#!/usr/bin/env python3
"""Report frozen CC waveform controls; missing containers are never imputed as data."""
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np

from calonu_weak_readout import evaluate
from report_calonu_native import table


def main():
    tick,cpu=time.perf_counter(),time.process_time()
    repo=Path(__file__).resolve().parents[1]
    out=repo/'workbook/stage39_energy_ml';cache=repo/'ntuples/energy_ml_stage39'
    cfg=json.loads((repo/'ml/configs/calonu_cc_waveform.json').read_text())
    prep=json.loads((out/'preparation.json').read_text())
    arrays={};cases=[];resources=[];schemas=[]
    for index in cfg['indices']:
        with np.load(cache/f'shards/{index}.npz') as z:
            data={k:z[k] for k in z.files}
        cases.extend(json.loads(str(data.pop('cases_json'))))
        resources.append(json.loads(str(data.pop('metadata_json'))))
        schemas.extend(json.loads(str(data.pop('schemas_json'))))
        for k,v in data.items():arrays.setdefault(k,[]).append(v)
    d={k:np.concatenate(v) for k,v in arrays.items()}
    n=len(cases);assert n==prep['events'] and n<=cfg['max_events']
    assert len({(c['index'],c['input_entry']) for c in cases})==n
    present=d['channel_present'];common=present.all(axis=1)&(d['saved_samples']==76).all(axis=1)
    expected=np.array([3892314112,3758096384,4160749568,4026531840],np.uint32)
    assert np.all(d['id32'][present]==np.broadcast_to(expected,(n,4))[present])
    # Every selected cache row and every persisted module is checked, including zero/inf.
    with np.load(repo/'ntuples/energy_ml_stage35/fit.npz') as z:
        old={k:z[k] for k in z.files if k!='metadata_json'}
    full_zero=old['CaloNu_total_E_EM']==0
    zero_rows=[]
    for label,support in [('fit_all',np.ones(len(full_zero),bool)),
                          ('fit_p100_1000',(old['reco_p_GeV']>=100)&(old['reco_p_GeV']<1000)),
                          ('fit_upstream',old['vertex_z_mm']<-2605.68),('fit_downstream',old['vertex_z_mm']>=-2605.68)]:
        zero_rows.append(dict(subset=label,N=int(support.sum()),zero_total=int((support&full_zero).sum()),
                              fraction_zero=float(np.mean(full_zero[support])),
                              note='Existing PHYS fit partition only; absence/HITS identity certified only on native subset'))
    table(out/'existing_fit_zero_readout.tsv',zero_rows)
    max_cache_diff=0.
    for j,c in enumerate(cases):
        k=c['cache_row'];assert int(old['manifest_index'][k])==c['index']
        for i in range(4):
            if not present[j,i]:
                assert all(old[f'CaloNu{i}_{s}'][k]==0 for s in ['charge','raw_charge'])
                # NtupleDumper::clearTree sets status=1 even when no hit/container exists.
                assert old[f'CaloNu{i}_status'][k]==1
                continue
            assert int(d['status'][j,i])==int(old[f'CaloNu{i}_status'][k])
            for src,dest in [('integral','charge'),('raw_integral','raw_charge')]:
                value,reference=d[src][j,i]/50,old[f'CaloNu{i}_{dest}'][k]
                if np.isfinite(value) and np.isfinite(reference):
                    max_cache_diff=max(max_cache_diff,float(abs(value-reference)))
                    assert np.isclose(value,reference,rtol=3e-6,atol=3e-5)
                else:assert value==reference or (np.isnan(value) and np.isnan(reference))
    regular=np.array([c['role']=='regular' for c in cases])
    gid=np.array([cfg['indices'].index(c['index']) for c in cases])
    p=np.array([c['reco_p_GeV'] for c in cases]);y=np.array([c['y_lepton'] for c in cases])
    z=np.array([c['vertex_z_mm'] for c in cases]);energy=np.array([c['truth_E_GeV'] for c in cases])
    proxy=np.array([c['primary_kinematic_parent_proxy'] for c in cases])
    target=np.zeros(n);estimates={};offpulse={};shifted={};model_estimates={}
    max_raw=0.
    for j,c in enumerate(cases):
        # Empty production containers have no saved time window: only HITS coverage is retained.
        if not common[j]:
            assert not present[j].any() or np.any(d['saved_samples'][j]!=76)
            continue
        times=d['saved_time'][j,0];assert np.all(d['saved_time'][j]==times)
        samples=(d['saved_time'][j]/2).astype(int)
        wave=(d['baseline_mean'][j,:,None]-np.take_along_axis(d['adc'][j],samples,axis=1)*(2/16.384)).astype(np.float32)
        np.testing.assert_array_equal(wave,d['saved_wave'][j])
        raw=np.maximum(wave,0).sum(axis=1,dtype=float)*2/50
        max_raw=max(max_raw,float(abs(raw-d['raw_integral'][j]/50).max()))
        np.testing.assert_allclose(raw,d['raw_integral'][j]/50,atol=3e-5,rtol=0)
        model=np.take_along_axis(d['signal_nominal_ADC'][j],samples,axis=1)*(2/16.384)
        target[j]=model.sum()*2/50
        output=evaluate(wave,d['adc'][j],d['baseline_mean'][j],d['baseline_rms'][j],times,cfg['template_parameters'])
        model_output=evaluate(model,-d['signal_nominal_ADC'][j],np.zeros(4),np.zeros(4),times,cfg['template_parameters'])
        for name,r in output.items():
            estimates.setdefault(name,np.full(n,np.nan))[j]=r['charge'].sum()
            offpulse.setdefault(name,np.full(n,np.nan))[j]=r['offpulse'].sum()
            shifted.setdefault(name,np.full((n,2),np.nan))[j]=[r['shifted_minus'].sum(),r['shifted_plus'].sum()]
            model_estimates.setdefault(name,np.full(n,np.nan))[j]=model_output[name]['charge'].sum()
    # Target for absent waveform is not assigned a fabricated window or a zero measurement.
    target[~common]=np.nan
    for val in estimates.values():assert np.isfinite(val[common]).all()
    rng=np.random.default_rng(cfg['bootstrap_seed'])
    draws=np.zeros((cfg['bootstrap_replicates'],6),int)
    for pair in [[0,1],[2,3],[4,5]]:draws[:,pair]=rng.multinomial(2,[.5,.5],size=len(draws))
    masks=[('regular',regular),('regular_p100_250',regular&(p<250)),('regular_p250_1000',regular&(p>=250)),
           ('regular_y_lt04',regular&(y<.4)),('regular_y04_08',regular&(y>=.4)&(y<.8)),('regular_y_ge08',regular&(y>=.8)),
           ('regular_upstream',regular&(z<-2605.68)),('regular_downstream',regular&(z>=-2605.68)),
           ('regular_primary_proxy',regular&proxy),('regular_not_proxy',regular&~proxy),('diagnostic',~regular)]
    for name,pair in [('pi',[0,1]),('k',[2,3]),('charm',[4,5])]:masks.append(('regular_'+name,regular&np.isin(gid,pair)))
    edges=[100,200,400,800,1600,3200,6400]
    for lo,hi in zip(edges[:-1],edges[1:]):masks.append((f'regular_Enu{lo}_{hi}',regular&(energy>=lo)&(energy<hi)))
    coverage=[];metrics=[];paired=[];baseline=[];timing=[]
    hit_total=d['hit_count'].sum(axis=1);hit_energy=d['hit_energy_MeV'].sum(axis=1)
    for subset,support in masks:
        mask=support&common
        coverage.append(dict(subset=subset,N_selected=int(support.sum()),N_common=int(mask.sum()),N_absent_all_channels=int((support&~present.any(axis=1)).sum()),
                             N_empty_HITS=int((support&(hit_total==0)).sum()),N_high_signal_ge1pC=int((mask&(target>=1)).sum())))
        if not mask.any():continue
        weight=draws[:,gid[mask]];den=weight.sum(axis=1);weight=weight[den>0];den=den[den>0]
        reference=estimates['signed_saved'][mask]-target[mask]
        refboot=np.sqrt(weight@(reference**2)/den)
        for name,values in estimates.items():
            error=values[mask]-target[mask];boot=np.sqrt(weight@(error**2)/den);biasboot=weight@error/den
            rmse=float(np.sqrt(np.mean(error**2)))
            metric=dict(subset=subset,method=name,N=int(mask.sum()),rmse_pC=rmse,bias_pC=float(error.mean()),
                        R68_pC=float((np.quantile(error,.84)-np.quantile(error,.16))/2),tail_abs_gt025=float(np.mean(abs(error)>.25)),
                        tail_abs_gt1=float(np.mean(abs(error)>1)),offpulse_RMS_pC=float(np.sqrt(np.mean(offpulse[name][mask]**2))),
                        offpulse_bias_pC=float(offpulse[name][mask].mean()),model_bias_pC=float((model_estimates[name][mask]-target[mask]).mean()))
            for key,arr in [('rmse',boot),('bias',biasboot)]:
                for suffix,q in [('lo',.025),('hi',.975)]:metric[key+'_'+suffix+'_pC']=float(np.quantile(arr,q)) if subset!='diagnostic' else 'not_applicable'
            metrics.append(metric)
            if subset!='diagnostic':
                gain=1-boot/refboot
                paired.append(dict(subset=subset,method=name,reference='signed_saved',gain=1-rmse/np.sqrt(np.mean(reference**2)),
                                   gain_lo=float(np.quantile(gain,.025)),gain_hi=float(np.quantile(gain,.975))))
            delta=shifted[name][mask]-values[mask,None]
            baseline.append(dict(subset=subset,method=name,max_abs_shift_pC=float(abs(delta).max())))
        high=mask&(target>=cfg['high_signal_threshold_pC'])
        if high.any():
            nominal=model_estimates['template_plus_constant'][high]
            for name in ['template_plus_constant','template_time_-2ns','template_time_+2ns']:
                rel=(model_estimates[name][high]-target[high])/target[high]
                change=(model_estimates[name][high]-nominal)/target[high]
                timing.append(dict(subset=subset,method=name,N=int(high.sum()),model_relative_bias=float(rel.mean()),
                                   model_relative_RMSE=float(np.sqrt(np.mean(rel**2))),median_relative_error=float(np.median(rel)),
                                   max_abs_relative_error=float(abs(rel).max()),fraction_abs_error_gt5pct=float(np.mean(abs(rel)>.05)),
                                   max_abs_change_from_nominal=float(abs(change).max()),fraction_abs_change_gt5pct=float(np.mean(abs(change)>.05))))
    event_rows=[]
    for j,c in enumerate(cases):
        event_rows.append(dict(index=c['index'],input_entry=c['input_entry'],cache_row=c['cache_row'],role=c['role'],common_waveform=bool(common[j]),
                               channels_present=int(present[j].sum()),reco_p_GeV=p[j],truth_E_GeV=energy[j],y_lepton=y[j],vertex_z_mm=z[j],
                               primary_kinematic_parent_proxy=bool(proxy[j]),sensitive_hit_count=int(hit_total[j]),sensitive_hit_energy_MeV=hit_energy[j],
                               nominal_signal_pC=target[j],**{name+'_pC':v[j] for name,v in estimates.items()}))
    for filename,rows in [('coverage',coverage),('readout_metrics',metrics),('paired_readout_gain',paired),('baseline_sensitivity',baseline),
                          ('high_signal_timing',timing),('events',event_rows)]:
        if rows:table(out/(filename+'.tsv'),rows)
    d['cases_json']=np.array(json.dumps(cases));d['nominal_window_charge_pC']=target;d['common_waveform']=common
    for name,v in estimates.items():d['readout_'+name+'_pC']=v
    np.savez_compressed(cache/'cc_waveform.npz',**d)
    with np.load(cache/'cc_waveform.npz') as saved:
        for k,v in d.items():np.testing.assert_array_equal(saved[k],v)
    primary=next(r for r in metrics if r['subset']=='regular' and r['method']==cfg['primary_readout'])
    ref=next(r for r in metrics if r['subset']=='regular' and r['method']=='signed_saved')
    gain=next(r for r in paired if r['subset']=='regular' and r['method']==cfg['primary_readout'])
    drift=next(r for r in baseline if r['subset']=='regular' and r['method']==cfg['primary_readout'])
    high_controls=[r for r in timing if r['subset'] in ['regular','diagnostic']]
    timing_problem=any(r['fraction_abs_error_gt5pct']>0 or r['fraction_abs_change_gt5pct']>0 for r in high_controls)
    summary=dict(events=n,regular=int(regular.sum()),diagnostic=int((~regular).sum()),common_waveform=int(common.sum()),
                 regular_common=int((common&regular).sum()),absent_all_channels=int((~present.any(axis=1)).sum()),
                 regular_all_four_threshold_failed=int((regular&common&np.all((d['status']&1)!=0,axis=1)).sum()),
                 regular_nominal_signal_median_pC=float(np.median(target[regular&common])),
                 absent_and_empty_HITS=int((~present.any(axis=1)&(hit_total==0)).sum()),
                 present_with_empty_HITS=int((present.any(axis=1)&(hit_total==0)).sum()),
                 empty_HITS_with_present=int(((hit_total==0)&present.any(axis=1)).sum()),
                 saturated_modules=int(((d['status']&4)!=0).sum()),saved_nonfinite_present=int((~np.isfinite(d['integral'])&present).sum()),
                 ADC_saved_waveforms_exact=True,cache_max_difference_pC=max_cache_diff,raw_max_difference_pC=max_raw,
                 regular_primary=primary,regular_signed=ref,paired_gain=gain,baseline_max_abs_shift_pC=drift['max_abs_shift_pC'],
                 weak_signal_gate_passed=bool(gain['gain_lo']>0 and primary['offpulse_RMS_pC']<ref['offpulse_RMS_pC'] and drift['max_abs_shift_pC']<1e-10),
                 high_signal_timing_limitation=bool(timing_problem),regular_high_signal_events=int(np.sum(regular&common&(target>=1))),
                 all_field_readback_equal=True,cache_bytes=(cache/'cc_waveform.npz').stat().st_size,
                 extraction_resources=resources,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                 peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                 neutrino_energy_gain='not measured',data_MC_physics_closure='not measured')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    unique={}
    for r in schemas:
        u=unique.setdefault(r['class_name'],dict(class_name=r['class_name'],loaded_checksum=r['loaded_checksum'],saved_checksums=r['saved_checksums'],checked_branches=[]))
        assert u['loaded_checksum']==r['loaded_checksum']
        u['checked_branches'].append(dict(file=r['file'],branch=r['branch']))
    (out/'native_schema_checks.json').write_text(json.dumps(list(unique.values()),indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='extraction_resources'}))


if __name__=='__main__':main()
