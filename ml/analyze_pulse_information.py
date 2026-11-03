"""Fixed descriptive controls and independent cache checks for stage79; zero fits."""
import csv
import json
import resource
import time

import numpy as np

from pulse_information_audit import DATA, OUT, SUFFIXES, save, strong_shape_validity
from audited_features import SCINTILLATORS, FIT_INVALID, WAVE_INVALID, configuration, load


def table(name, rows):
    with (OUT/name).open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n')
        writer.writeheader();writer.writerows({k:'NaN' if v is None else v for k,v in row.items()} for row in rows)


def quantiles(values):
    a=np.asarray(values);a=a[np.isfinite(a)]
    return np.quantile(a,[.16,.5,.84]).tolist() if len(a) else [None]*3


def summary(z, mask, channel, valid):
    st=z['status'][:,channel].astype(int);n=int(mask.sum())
    result=dict(N=n,strong_shape_N=int((valid[:,channel]&mask).sum()),
        wave_invalid_N=int((mask&((st&WAVE_INVALID)!=0)).sum()),threshold_failed_N=int((mask&((st&1)!=0)).sum()),
        overflow_N=int((mask&((st&4)!=0)).sum()),fit_failure_N=int((mask&((st&(16|32))!=0)).sum()),
        baseline_zero_N=int((mask&(z['baseline_rms'][:,channel]==0)).sum()),
        negative_raw_N=int((mask&(z['raw_charge'][:,channel]<0)).sum()))
    for key in ['width','localtime','raw_peak','baseline_rms']:
        q=quantiles(z[key][mask&valid[:,channel],channel])
        result.update({key+'_'+suffix:value for suffix,value in zip(['q16','median','q84'],q)})
    return result


def main():
    start,cpu=time.perf_counter(),time.process_time()
    parts=[]
    paths=[DATA/'measurements.npz'] if (DATA/'measurements.npz').exists() else [DATA/f'part{j}.npz' for j in range(4)]
    for path in paths:
        with np.load(path) as a:parts.append({k:a[k] for k in ['row','entry','x']+SUFFIXES})
    z={k:np.concatenate([a[k] for a in parts]) for k in parts[0]};order=np.argsort(z['row']);z={k:v[order] for k,v in z.items()}
    d,s,x=load();rows=z['row'];plan=json.loads((OUT/'measurement_plan.json').read_text())
    np.testing.assert_array_equal(rows,plan['rows']);assert len(np.unique(rows))==2048
    assert np.all(d['train_eligible'][rows]) and np.all(d['nominal'][rows])
    index={int(r):i for i,r in enumerate(s['row'])};positions=np.array([index[int(r)] for r in rows])
    np.testing.assert_array_equal(z['x'],x[positions]);np.testing.assert_array_equal(z['raw_charge'],s['raw_charge'][positions])
    np.testing.assert_array_equal(z['status'],s['status'][positions]);np.testing.assert_array_equal(z['baseline_rms'],s['baseline_rms'][positions])
    status=z['status'].astype(np.int64)
    valid=strong_shape_validity(z)
    names=configuration()['features'];p=d['reco_pz_GeV'][rows];source=d['source'][rows];component=d['component'][rows]
    pbin=np.searchsorted([50,100,250,np.inf],p,side='right')-1
    allmask=np.ones(len(rows),bool);groups=[('all','all',allmask)]
    groups += [('source',str(v),source==v) for v in np.unique(source)]
    groups += [('component',str(v),component==v) for v in np.unique(component)]
    groups += [('pz',str(v),pbin==v) for v in np.unique(pbin)]
    summaries=[]
    for kind,group,mask in groups:
        for j,detector in enumerate(SCINTILLATORS):
            summaries.append(dict(kind=kind,group=group,detector=detector,**summary(z,mask,j,valid)))
    table('pulse_summary.tsv',summaries)
    status_rows=[]
    for kind,group,mask in groups:
        for j,detector in enumerate(SCINTILLATORS):
            values,counts=np.unique(status[mask,j],return_counts=True)
            status_rows += [dict(kind=kind,group=group,detector=detector,status=int(v),N=int(n)) for v,n in zip(values,counts)]
    table('status_counts.tsv',status_rows)
    geometry=['ML_mu_'+key+'_mm' for key in ['x0','y0','z0','X_atVetoNu','Y_atVetoNu','X_atCalo','Y_atCalo']]
    geom=z['x'][:,[names.index(n) for n in geometry]].astype(float)
    tolerances=np.array([.1,.2,20,20,100,20,20,20,20,.1])
    pair_rows=[];pair_summary=[]
    # One deterministic matching rule, no response fit and no threshold scan.
    for j,detector in enumerate(SCINTILLATORS):
        control=np.column_stack([np.arcsinh(z['raw_charge'][:,j].astype(float)),np.log(p),geom,z['baseline_rms'][:,j]])/tolerances
        eligible=np.flatnonzero(valid[:,j]&np.isfinite(control).all(axis=1))
        delta=control[eligible,None,:]-control[None,eligible,:]
        allowed=(np.abs(delta)<=1).all(axis=2)
        allowed &= (source[eligible,None]!=source[None,eligible])&(component[eligible,None]==component[None,eligible])
        allowed &= (pbin[eligible,None]==pbin[None,eligible])&(status[eligible,None,j]==status[None,eligible,j])
        left,right=np.where(np.triu(allowed,k=1));distance=np.sum(delta[left,right]**2,axis=1)
        permutation=np.lexsort((rows[eligible[right]],rows[eligible[left]],distance));used=set();pairs=[]
        for k in permutation:
            a,b=int(eligible[left[k]]),int(eligible[right[k]])
            if a in used or b in used:continue
            used.update([a,b]);pairs.append((a,b,float(distance[k])))
        for a,b,distance in pairs:
            r=dict(detector=detector,row_a=int(rows[a]),row_b=int(rows[b]),source_a=int(source[a]),source_b=int(source[b]),
                component=str(component[a]),pz_bin=int(pbin[a]),control_distance=distance,
                same_incoming=bool(np.array_equal(d['incoming'][rows[a]],d['incoming'][rows[b]])),
                delta_asinh_charge=float(np.arcsinh(float(z['raw_charge'][a,j]))-np.arcsinh(float(z['raw_charge'][b,j]))),
                delta_logpz=float(np.log(p[a]/p[b])),max_geometry_scaled_difference=float(np.max(np.abs((geom[a]-geom[b])/tolerances[2:9]))),
                delta_rms_mV=float(z['baseline_rms'][a,j]-z['baseline_rms'][b,j]))
            for key in ['width','raw_peak','localtime']:r['delta_'+key]=float(z[key][a,j])-float(z[key][b,j])
            pair_rows.append(r)
        for kind,key,mask in groups:
            selected=[r for r in pair_rows if r['detector']==detector and
                (kind=='all' or (kind=='source' and int(key) in [r['source_a'],r['source_b']]) or
                 (kind=='component' and key==r['component']) or (kind=='pz' and int(key)==r['pz_bin']))]
            r=dict(kind=kind,group=key,detector=detector,disjoint_pairs_N=len(selected),same_incoming_pairs_N=sum(a['same_incoming'] for a in selected))
            for variable in ['width','raw_peak','localtime']:
                q=quantiles([abs(a['delta_'+variable]) for a in selected]);r.update({variable+'_abs_'+k:v for k,v in zip(['q16','median','q84'],q)})
            pair_summary.append(r)
    table('conditional_pairs.tsv',pair_rows);table('conditional_variation.tsv',pair_summary)
    relative=[]
    for a,b in [(5,6),(7,8)]:
        mask=valid[:,a]&valid[:,b]
        diff=z['localtime'][:,a].astype(float)-z['localtime'][:,b]
        for kind,key,groupmask in groups:
            q=quantiles(diff[mask&groupmask]);relative.append(dict(kind=kind,group=key,pair=SCINTILLATORS[a]+'-'+SCINTILLATORS[b],
                valid_N=int((mask&groupmask).sum()),q16_ns=q[0],median_ns=q[1],q84_ns=q[2],physically_corrected=False))
    table('uncorrected_relative_time.tsv',relative)
    probability=np.zeros(len(rows))
    for stratum in plan['strata']:
        mask=(source==stratum['source'])&(p>=stratum['pz_low'])
        if stratum['pz_high'] is not None:mask&=p<stratum['pz_high']
        assert int(mask.sum())==stratum['n']
        probability[mask]=stratum['inclusion_probability']
    assert np.all(probability>0)
    # Retain compact actual summaries/identities, no waveform, ROOT or energy predictions.
    np.savez_compressed(DATA/'measurements.npz',**z,strong_shape_valid=valid,inclusion_probability=probability)
    resource_records=[json.loads((OUT/f'extraction{j}.json').read_text()) for j in range(4)]
    st,counts=np.unique(status,return_counts=True)
    result=dict(N=len(rows),sources=len(np.unique(source)),runs=len(np.unique(d['run'][rows])),components={str(k):int((component==k).sum()) for k in np.unique(component)},
        pz_N=[int((pbin==k).sum()) for k in range(3)],unique_incoming_N=len(set(map(tuple,d['incoming'][rows]))),
        original62_nan_rows=int(np.isnan(z['x']).any(axis=1).sum()),strong_shape_N=int(valid.sum()),channel_event_N=int(valid.size),
        status_counts=dict(zip(map(str,st),map(int,counts))),trigger_all_zero=bool(np.all(z['triggertime']==0)),bcid_all_zero=bool(np.all(z['bcidtime']==0)),
        sentinel_counts={k:{str(v):int((z[k]==v).sum()) for v in [-999,-1]} for k in ['width','raw_peak','localtime','baseline_rms']},
        source_shape_valid_N={str(v):int(valid[source==v].sum()) for v in np.unique(source)},
        original62_exact=True,raw_status_baseline_cache_exact=True,all_legal_train_nominal=True,
        inclusion_probability_range=[float(probability.min()),float(probability.max())],
        formal_requested_bytes=sum(r['requested_bytes'] for r in resource_records),formal_wall_sum_s=sum(r['wall_s'] for r in resource_records),
        formal_CPU_sum_s=sum(r['cpu_s'] for r in resource_records),formal_peak_rss_MiB=max(r['peak_rss_MiB'] for r in resource_records),
        analysis_wall_s=time.perf_counter()-start,analysis_CPU_s=time.process_time()-cpu,analysis_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        no_energy_fit=True,no_F7_inference=True,no_test_cal_eval_acquisition=True,
        physical_corrected_time=False,energy_gain='unmeasured',variation_interpretation='finite-tolerance descriptive matching, not strict conditional independence or causal information')
    save(OUT/'measurement_summary.json',result)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    all_summary=[r for r in summaries if r['kind']=='all']
    all_pairs=[r for r in pair_summary if r['kind']=='all']
    fig,axes=plt.subplots(1,3,figsize=(12,5.4),sharey=True)
    yy=np.arange(len(SCINTILLATORS))
    axes[0].barh(yy,[r['strong_shape_N']/2048 for r in all_summary],color='#356c9b')
    axes[0].set_xlabel('Strong, unsaturated, fit-valid fraction')
    axes[0].set_yticks(yy,SCINTILLATORS);axes[0].invert_yaxis()
    for ax,var,label in zip(axes[1:],['width','raw_peak'],['Absolute width difference (ns)','Absolute raw peak difference (mV)']):
        for i,r in enumerate(all_pairs):
            if not r['disjoint_pairs_N']:
                ax.text(.03,i,'not measured (0 pairs)',transform=ax.get_yaxis_transform(),va='center',fontsize=8)
                continue
            q16,med,q84=[r[var+'_abs_'+k] for k in ['q16','median','q84']]
            ax.errorbar(med,i,xerr=[[med-q16],[q84-med]],fmt='o',color='#356c9b',capsize=2)
            ax.text(.97,i,'n='+str(r['disjoint_pairs_N']),transform=ax.get_yaxis_transform(),ha='right',va='center',fontsize=7)
        ax.set_xlabel(label);ax.set_xscale('log');ax.grid(axis='x',alpha=.2)
    fig.suptitle('Stage79: selected train sample; fixed cross-source matching\nPoints: median; bars: 16–84% spread (not confidence intervals)',fontsize=11)
    fig.tight_layout();fig.savefig(OUT/'pulse_variation.png',dpi=150);fig.savefig(OUT/'pulse_variation.pdf');plt.close(fig)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
