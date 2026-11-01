#!/usr/bin/env python3
"""Paired source development evidence for zero readout and ideal signal/depth."""
import argparse
import json
import resource
import time
from pathlib import Path
import numpy as np
from probability_information import probability_metrics, score_information
from train_bdt import metric_values, write_table


def strata(d):
    p=d['reco_p_GeV']; y=d['y_lepton']; z=d['vertex_z_mm']; en=d['truth_E_GeV']
    focus=(p>=100)&(p<1000)
    result={'all':np.ones(len(p),bool),'focus':focus,'p100_250':(p>=100)&(p<250),
            'p250_1000':(p>=250)&(p<1000),'p1000_up':p>=1000}
    for lo,hi in zip([100,200,400,800,1600,3200],[200,400,800,1600,3200,6400]):
        result[f'focus_E{lo}_{hi}']=focus&(en>=lo)&(en<hi)
    for lo,hi in [(0,.2),(.2,.5),(.5,.8),(.8,1.01)]: result[f'focus_y{lo}_{hi}']=focus&(y>=lo)&(y<hi)
    result['focus_y_unknown']=focus&~np.isfinite(y)
    for lo,hi in [(-3000,-2928),(-2812,-2600),(-2600,-2300),(-2300,-1950),(-1769.65,-1619.65)]:
        result[f'focus_z{lo}_{hi}']=focus&(z>=lo)&(z<hi)
    for comp in ['pi','k','charm']: result['focus_'+comp]=focus&(d['component']==comp)
    proxy=d['primary_kinematic_parent_proxy']
    result['focus_proxy']=focus&proxy; result['focus_not_proxy']=focus&~proxy
    return result


def source_draws(d,n,seed):
    unique,gid=np.unique(d['group'],return_inverse=True); rng=np.random.default_rng(seed)
    draws=np.zeros((n,len(unique)),int)
    for comp in ['pi','k','charm']:
        ids=np.flatnonzero(np.char.startswith(unique,comp+':'))
        draws[:,ids]=rng.multinomial(len(ids),np.full(len(ids),1/len(ids)),size=n)
    return unique,gid,draws


def joined(repo,part,d):
    sets=[]; records=[]
    for f in range(3):
        with np.load(repo/f'ml/artifacts/stage42/{part}/{f}/predictions.npz') as z: s={k:z[k] for k in z.files}
        m=json.loads(str(s.pop('metadata_json'))); assert not m['smoke'] and m['fold']==f and m['part']==part
        records += m['records']
        ids=s['cache_row']; assert (d['fold'][ids]==f).all()
        s['prior']=np.tile(s['prior'],(len(ids),1)); sets.append(s)
    order=np.argsort(np.concatenate([s['cache_row'] for s in sets])); data={}
    assert all(set(s)==set(sets[0]) for s in sets)
    for k in sets[0]: data[k]=np.concatenate([s[k] for s in sets])[order]
    expected=np.arange(len(d['x'])) if part=='A' else np.flatnonzero(d['selected'])
    np.testing.assert_array_equal(data['cache_row'],expected)
    return data,records


def evaluate(repo,part,d,cfg,out):
    pred,resources=joined(repo,part,d); rows=pred['cache_row']; local={k:v[rows] for k,v in d.items()}
    masks=strata(local); names=[k for k in pred if k not in ['cache_row','prior'] and not k.startswith('q_')]
    unique,gid,draws=source_draws(local,cfg['bootstrap_replicates'],cfg['seed'])
    y=local['truth_E_GeV']; n=len(y); ng=len(unique)
    metrics=[]; paired=[]; spectra=[]; spectral_pairs=[]; risks={}
    pairs={'A':[('A0','A_zero'),('A0','A_readout'),('A_zero','A_readout')],
           'B':[('I0','Iz'),('I0','Is'),('I0','Isz'),('Iz','Isz'),('Is','Isz')],
           'C':[]}[part]
    if part=='C':
        bp,_=joined(repo,'B',d)
        for key in ['I0','Is']: pred[key]=bp[key]; pred['q_'+key]=bp['q_'+key]
        names += ['I0','Is']; pairs=[('I0',k) for k in cfg['synthetic_if_gate']['candidates']]+[('Is','fixed_nominal'),('fixed_nominal','fixed_double_noise'),('positive_nominal','legacy_zero_nominal')]
    errors={name:np.log(pred[name]/y) for name in names}
    for label,mask in masks.items():
        if not mask.any(): continue
        counts=np.bincount(gid,weights=mask,minlength=ng); den=draws@counts; valid=den>0
        for name in names:
            result=metric_values(y,pred[name],mask)
            metrics.append(dict(part=part,stratum=label,model=name,sources=int(np.count_nonzero(counts)),**result))
            mse=np.bincount(gid,weights=mask*errors[name]**2,minlength=ng)
            risks[(label,name)]=np.sqrt((draws[valid]@mse)/den[valid])
        for left,right in pairs:
            l=risks[(label,left)]; r=risks[(label,right)]; gain=1-r/l
            point=1-np.sqrt(np.mean(errors[right][mask]**2)/np.mean(errors[left][mask]**2))
            delta=np.bincount(gid,weights=mask*(pred[right]/y-pred[left]/y),minlength=ng)
            bias_delta=(draws[valid]@delta)/den[valid]
            paired.append(dict(part=part,stratum=label,reference=left,model=right,N=int(mask.sum()),sources=int(np.count_nonzero(counts)),
                               relative_gain=float(point),CI025=float(np.quantile(gain,.025)),CI975=float(np.quantile(gain,.975)),
                               log_RMSE_delta=float(np.sqrt(np.mean(errors[right][mask]**2))-np.sqrt(np.mean(errors[left][mask]**2))),
                               delta_CI025=float(np.quantile(r-l,.025)),delta_CI975=float(np.quantile(r-l,.975)),
                               mean_bias_delta=float(np.mean((pred[right]/y-pred[left]/y)[mask])),
                               bias_CI025=float(np.quantile(bias_delta,.025)),bias_CI975=float(np.quantile(bias_delta,.975)),valid_bootstrap=int(valid.sum())))
    labels=np.searchsorted(cfg['energy_edges_GeV'],y,side='right')-1
    # The proper score is evaluable even when the empirical six-bin information is ill conditioned.
    for label in ['all','focus']:
        mask=masks[label]; lab=labels[mask]; weights=np.ones(mask.sum()); counts=np.bincount(gid,weights=mask,minlength=ng)
        den=draws@counts; scores={}; spectral_sigma={}
        for name in names:
            qkey='q_'+name
            if qkey not in pred:
                spectra.append(dict(part=part,stratum=label,model=name,measured=False,reason='calibration class missing')); continue
            q=pred[qkey][mask]; ratio=q/pred['prior'][mask]
            info,_=score_information(ratio,lab,weights)
            loss=-np.log(q[np.arange(len(lab)),lab]); pergroup=np.bincount(gid[mask],weights=loss,minlength=ng)
            scores[name]=(draws@pergroup)/den
            sb=[]
            for draw in draws:
                info_b,_=score_information(ratio,lab,draw[gid[mask]].astype(float))
                sb.append(info_b.get('relative_sigma_RMS',np.nan))
            spectral_sigma[name]=np.array(sb)
            good=np.isfinite(sb)
            spectra.append(dict(part=part,stratum=label,model=name,measured=True,N=int(mask.sum()),
                                **probability_metrics(q,lab),score_valid=info['valid'],
                                score_relative_sigma_RMS=info.get('relative_sigma_RMS',None),
                                score_condition=info.get('condition',None),
                                score_bootstrap_valid=int(good.sum()),
                                score_CI025=float(np.nanquantile(sb,.025)) if good.any() else None,
                                score_CI975=float(np.nanquantile(sb,.975)) if good.any() else None,true_bin_counts=np.bincount(lab,minlength=6).tolist()))
        for left,right in pairs:
            if left not in scores or right not in scores: continue
            delta=scores[right]-scores[left]
            sg=1-spectral_sigma[right]/spectral_sigma[left]; finite=np.isfinite(sg)
            spectral_pairs.append(dict(part=part,stratum=label,reference=left,model=right,log_score_delta=float(np.mean(-np.log(pred['q_'+right][mask][np.arange(len(lab)),lab])+np.log(pred['q_'+left][mask][np.arange(len(lab)),lab]))),
                                       CI025=float(np.quantile(delta,.025)),CI975=float(np.quantile(delta,.975)),
                                       score_sigma_gain_CI025=float(np.nanquantile(sg,.025)) if finite.any() else None,
                                       score_sigma_gain_CI975=float(np.nanquantile(sg,.975)) if finite.any() else None,
                                       score_sigma_valid_bootstrap=int(finite.sum())))
    write_table(out/f'{part}_metrics.tsv',metrics); write_table(out/f'{part}_paired.tsv',paired)
    # Identical keys for all measured formal candidates.
    (out/f'{part}_spectrum.json').write_text(json.dumps(spectra,indent=2)+'\n')
    write_table(out/f'{part}_spectrum_paired.tsv',spectral_pairs); write_table(out/f'{part}_training_resources.tsv',resources)
    compact={k:pred[k] for k in pred}; compact.update({k:local[k] for k in ['run','eventID','group','component','reco_p_GeV','truth_E_GeV','y_lepton','vertex_z_mm','primary_kinematic_parent_proxy']})
    np.savez_compressed(repo/f'ntuples/energy_ml_stage42/{part}_predictions.npz',**compact)
    if part=='B':
        interactions=[]
        for label,mask in masks.items():
            if not mask.any(): continue
            e=errors; value=e['I0']**2-e['Is']**2-e['Iz']**2+e['Isz']**2
            counts=np.bincount(gid,weights=mask,minlength=ng); den=draws@counts; ok=den>0
            boot=(draws[ok]@np.bincount(gid,weights=value*mask,minlength=ng))/den[ok]
            interactions.append(dict(stratum=label,N=int(mask.sum()),redundancy_log_MSE=float(value[mask].mean()),CI025=float(np.quantile(boot,.025)),CI975=float(np.quantile(boot,.975))))
        write_table(out/'B_interaction.tsv',interactions)
        main=next(r for r in paired if r['stratum']=='focus' and r['reference']=='I0' and r['model']=='Is')
        cond=next(r for r in paired if r['stratum']=='focus' and r['reference']=='Iz' and r['model']=='Isz')
        passed=main['relative_gain']>=cfg['gate']['minimum_relative_log_RMSE_gain'] and main['CI025']>0 and cond['relative_gain']>=0
        (out/'C_gate.json').write_text(json.dumps(dict(passed=bool(passed),main=main,conditional=cond),indent=2)+'\n')
    return dict(part=part,events=n,sources=ng,models=names,formal_fits=len(resources))


def main():
    p=argparse.ArgumentParser(); p.add_argument('--part',choices=['A','B','C'],required=True); a=p.parse_args()
    tick,cpu=time.perf_counter(),time.process_time(); repo=Path(__file__).resolve().parents[1]; out=repo/'workbook/stage42_energy_ml'
    cfg=json.loads((repo/'ml/configs/calonu_information.json').read_text())
    with np.load(repo/'ntuples/energy_ml_stage42/development.npz') as z: d={k:z[k] for k in z.files}
    summary=evaluate(repo,a.part,d,cfg,out)
    summary.update(wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/f'{a.part}_evaluation.json').write_text(json.dumps(summary,indent=2)+'\n'); print(json.dumps(summary))

if __name__=='__main__': main()
