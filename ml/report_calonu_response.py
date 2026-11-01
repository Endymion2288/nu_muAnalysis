#!/usr/bin/env python3
"""Evaluate the frozen response experiment, keeping synthetic and native support separate."""
import json
import resource
import time
from pathlib import Path
import numpy as np
from calonu_timed_readout import bounded_time
from calonu_weak_readout import template_weights
from report_calonu_native import table


def main():
    tick,cpu=time.perf_counter(),time.process_time()
    repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage40_energy_ml';cache=repo/'ntuples/energy_ml_stage40'
    cfg=json.loads((repo/'ml/configs/calonu_response.json').read_text());chunks={};cases=[];resources=[];schemas=[]
    for index in cfg['indices']:
        with np.load(cache/f'shards/{index}.npz') as saved: part={k:saved[k] for k in saved.files}
        records=json.loads(str(part.pop('cases_json')));request=json.loads((out/f'request_{index}.json').read_text())
        assert len(records)==len(request['cases'])
        for expected,actual in zip(request['cases'],records):
            assert all(actual[k]==v for k,v in expected.items())
        cases.extend(records);resources.append(json.loads(str(part.pop('metadata_json'))))
        schemas.extend(json.loads(str(part.pop('schemas_json'))))
        for key,value in part.items():chunks.setdefault(key,[]).append(value)
    d={k:np.concatenate(v) for k,v in chunks.items()};n=len(cases)
    assert n==json.loads((out/'preparation.json').read_text())['events']<=cfg['max_events']
    assert len({(c['index'],c['input_entry']) for c in cases})==n
    regular=np.array([c['role']=='regular' for c in cases]);p=np.array([c['reco_p_GeV'] for c in cases])
    y=np.array([c['y_lepton'] for c in cases]);z=np.array([c['vertex_z_mm'] for c in cases]);energy=np.array([c['truth_E_GeV'] for c in cases])
    proxy=np.array([c['primary_kinematic_parent_proxy'] for c in cases]);gid=np.array([cfg['indices'].index(c['index']) for c in cases])
    present=d['channel_present'];common=present.all(axis=1)&(d['saved_samples']==76).all(axis=1)
    empty=d['hit_count'].sum(axis=1)==0
    np.testing.assert_array_equal(empty,~present.any(axis=1))
    expected_ids=np.array([3892314112,3758096384,4160749568,4026531840],np.uint32)
    np.testing.assert_array_equal(d['id32'][common],np.broadcast_to(expected_ids,(common.sum(),4)))
    times=d['saved_time'][common][0,0];np.testing.assert_array_equal(d['saved_time'][common],np.broadcast_to(times,d['saved_time'][common].shape))
    samples=(d['saved_time'][common]/2).astype(int)
    wave=(d['baseline_mean'][common,:,None]-np.take_along_axis(d['adc'][common],samples,axis=2)*(2/16.384)).astype(np.float32)
    np.testing.assert_array_equal(wave,d['saved_wave'][common])
    raw=np.maximum(wave,0).sum(axis=(1,2),dtype=float)*2/50
    np.testing.assert_allclose(np.maximum(wave,0).sum(axis=2,dtype=float)*2/50,d['raw_integral'][common]/50,rtol=0,atol=3e-5)
    with np.load(repo/'ntuples/energy_ml_stage35/fit.npz') as saved:
        for j,c in enumerate(cases):
            row=c['cache_row'];assert int(saved['manifest_index'][row])==c['index']
            for channel in range(4):
                if not present[j,channel]:
                    assert saved[f'CaloNu{channel}_charge'][row]==saved[f'CaloNu{channel}_raw_charge'][row]==0
                    assert saved[f'CaloNu{channel}_status'][row]==1
                else:
                    assert int(saved[f'CaloNu{channel}_status'][row])==int(d['status'][j,channel])
                    np.testing.assert_allclose(d['raw_integral'][j,channel]/50,saved[f'CaloNu{channel}_raw_charge'][row],rtol=3e-6,atol=3e-5)
    signal=np.take_along_axis(d['signal_nominal_ADC'][common],samples,axis=2).astype(float)*(2/16.384)
    target=np.full(n,np.nan);target[common]=signal.sum(axis=(1,2))*2/50
    off=d['baseline_mean'][common,:,None]-d['adc'][common,:,100:176]*(2/16.384)
    estimates={};models={};offpulse={};times_fit={};boundary={};baseline=[]
    def expand(value):
        a=np.full(n,np.nan);a[common]=value;return a
    for center in cfg['center_controls_ns']:
        fixed_name='fixed' if center==0 else f'fixed_center{center:+g}ns'
        timed_name='bounded_time' if center==0 else f'bounded_center{center:+g}ns'
        weights=template_weights(times,cfg['template_parameters'],center)[1]
        for name in [fixed_name,timed_name]:
            for label,value,destination in [('observed',wave,estimates),('model',signal,models),('offpulse',off,offpulse)]:
                if name==fixed_name:charge=(value@weights).sum(axis=1)
                else:
                    result=bounded_time(value,times,cfg['template_parameters'],center_ns=center,bound_ns=cfg['bound_ns'],step_ns=cfg['step_ns'])
                    charge=result['charge'].sum(axis=1)
                    if label=='observed':
                        times_fit[name]=expand(result['time_shift_ns']);boundary[name]=expand(result['at_boundary'])
                destination[name]=expand(charge)
            if center==0:
                for sign in [-1,1]:
                    perturbed=wave+sign*d['baseline_rms'][common,:,None]
                    changed=((perturbed@weights).sum(axis=1) if name==fixed_name else
                             bounded_time(perturbed,times,cfg['template_parameters'],bound_ns=cfg['bound_ns'],step_ns=cfg['step_ns'])['charge'].sum(axis=1))
                    for subset,mask in [('regular',regular[common]),('diagnostic',~regular[common])]:
                        baseline.append(dict(method=name,subset=subset,baseline_sigma=sign,
                                             max_abs_change_pC=float(abs(changed[mask]-estimates[name][common][mask]).max())))
    for name,values,noise,model in [('signed',wave.sum(axis=(1,2),dtype=float)*2/50,off.sum(axis=(1,2))*2/50,signal.sum(axis=(1,2))*2/50),
                                     ('positive_raw',raw,np.maximum(off,0).sum(axis=(1,2))*2/50,signal.sum(axis=(1,2))*2/50)]:
        estimates[name]=expand(values);offpulse[name]=expand(noise);models[name]=expand(model)
    masks=[('regular',regular),('regular_p100_250',regular&(p<250)),('regular_p250_1000',regular&(p>=250)),
           ('regular_y_lt04',regular&(y<.4)),('regular_y04_08',regular&(y>=.4)&(y<.8)),('regular_y_ge08',regular&(y>=.8)),
           ('regular_upstream',regular&(z<-2605.68)),('regular_downstream',regular&(z>=-2605.68)),
           ('regular_primary_proxy',regular&proxy),('regular_not_proxy',regular&~proxy),('diagnostic',~regular)]
    for label,groups in [('pi',[0,1]),('k',[2,3]),('charm',[4,5])]:masks.append(('regular_'+label,regular&np.isin(gid,groups)))
    for low,high in zip([100,200,400,800,1600,3200],[200,400,800,1600,3200,6400]):
        masks.append((f'regular_Enu{low}_{high}',regular&(energy>=low)&(energy<high)))
    rng=np.random.default_rng(cfg['bootstrap_seed']);draws=np.zeros((cfg['bootstrap_replicates'],6),int)
    for pair in [[0,1],[2,3],[4,5]]:draws[:,pair]=rng.multinomial(2,[.5,.5],size=len(draws))
    coverage=[];metrics=[];paired=[];timing=[]
    for label,support in masks:
        mask=support&common
        coverage.append(dict(subset=label,N_selected=int(support.sum()),N_common=int(mask.sum()),N_absent=int((support&empty).sum()),
                             N_high_signal=int((mask&(target>=1)).sum())))
        if not mask.any():continue
        weights=draws[:,gid[mask]];den=weights.sum(axis=1);weights=weights[den>0];den=den[den>0]
        for name,value in estimates.items():
            err=value[mask]-target[mask];rmse=np.sqrt(np.mean(err**2));boot=np.sqrt(weights@(err**2)/den);bboot=weights@err/den
            row=dict(subset=label,method=name,N=int(mask.sum()),rmse_pC=float(rmse),bias_pC=float(err.mean()),
                     R68_pC=float((np.quantile(err,.84)-np.quantile(err,.16))/2),tail_abs_gt025=float(np.mean(abs(err)>.25)),
                     tail_abs_gt1=float(np.mean(abs(err)>1)),offpulse_RMS_pC=float(np.sqrt(np.mean(offpulse[name][mask]**2))),
                     offpulse_bias_pC=float(offpulse[name][mask].mean()),model_bias_pC=float((models[name][mask]-target[mask]).mean()),
                     time_boundary_fraction=float(boundary[name][mask].mean()) if name in boundary else 'not_applicable')
            for key,arr in [('rmse',boot),('bias',bboot)]:
                for suffix,q in [('lo',.025),('hi',.975)]:row[f'{key}_{suffix}_pC']=float(np.quantile(arr,q)) if label!='diagnostic' else 'not_applicable'
            metrics.append(row)
            if label!='diagnostic':
                for reference in ['signed','fixed']:
                    ref=estimates[reference][mask]-target[mask];refboot=np.sqrt(weights@(ref**2)/den);gain=1-boot/refboot
                    paired.append(dict(subset=label,method=name,reference=reference,gain=1-rmse/np.sqrt(np.mean(ref**2)),
                                       gain_lo=float(np.quantile(gain,.025)),gain_hi=float(np.quantile(gain,.975))))
        high=mask&(target>=cfg['high_signal_threshold_pC'])
        for name in ['fixed','fixed_center-2ns','fixed_center+2ns','bounded_time','bounded_center-2ns','bounded_center+2ns']:
            if not high.any():continue
            rel=(models[name][high]-target[high])/target[high]
            ref='bounded_time' if name.startswith('bounded') else 'fixed'
            change=(models[name][high]-models[ref][high])/target[high]
            observed=(estimates[name][high]-target[high])/target[high]
            timing.append(dict(subset=label,method=name,N=int(high.sum()),model_relative_bias=float(rel.mean()),
                               model_relative_RMSE=float(np.sqrt(np.mean(rel**2))),model_max_abs_relative_error=float(abs(rel).max()),
                               model_bad_5pct=int(np.sum(abs(rel)>.05)),model_max_abs_center_change=float(abs(change).max()),
                               model_center_change_bad_5pct=int(np.sum(abs(change)>.05)),
                               observed_relative_RMSE=float(np.sqrt(np.mean(observed**2))),observed_bad_5pct=int(np.sum(abs(observed)>.05))))
    eventrows=[]
    for j,c in enumerate(cases):
        eventrows.append(dict(index=c['index'],input_entry=c['input_entry'],cache_row=c['cache_row'],role=c['role'],common_waveform=bool(common[j]),
                              reco_p_GeV=p[j],truth_E_GeV=energy[j],y_lepton=y[j],vertex_z_mm=z[j],primary_kinematic_parent_proxy=bool(proxy[j]),
                              sensitive_hit_count=int(d['hit_count'][j].sum()),nominal_signal_pC=target[j],
                              **{k+'_pC':v[j] for k,v in estimates.items()},bounded_time_shift_ns=times_fit['bounded_time'][j]))
    for name,rows in [('coverage',coverage),('metrics',metrics),('paired_gain',paired),('high_signal_timing',timing),('baseline_sensitivity',baseline),('events',eventrows)]:
        table(out/(name+'.tsv'),rows)
    primary=next(r for r in metrics if r['subset']=='regular' and r['method']=='bounded_time')
    fixed=next(r for r in metrics if r['subset']=='regular' and r['method']=='fixed')
    signed=next(r for r in metrics if r['subset']=='regular' and r['method']=='signed')
    gain=next(r for r in paired if r['subset']=='regular' and r['method']=='bounded_time' and r['reference']=='signed')
    high_controls=[r for r in timing if r['subset'] in ['regular','diagnostic'] and r['method'].startswith('bounded')]
    high_gate=bool(high_controls and all(r['model_max_abs_relative_error']<=cfg['gates']['high_signal_model_max_abs_error']
                       and r['model_max_abs_center_change']<=cfg['gates']['high_signal_model_max_abs_center_change'] for r in high_controls))
    drift=max(r['max_abs_change_pC'] for r in baseline if r['method']=='bounded_time')
    noise_gate=bool(primary['offpulse_RMS_pC']<signed['offpulse_RMS_pC'] and
                    primary['offpulse_RMS_pC']/fixed['offpulse_RMS_pC']<=cfg['gates']['offpulse_RMS_ratio_to_fixed_max'])
    source=json.loads((out/'source_noise.json').read_text())
    summary=dict(events=n,regular=int(regular.sum()),diagnostic=int((~regular).sum()),common=int(common.sum()),regular_common=int((common&regular).sum()),
                 absent=int(empty.sum()),regular_absent=int((empty&regular).sum()),regular_primary=primary,regular_fixed=fixed,regular_signed=signed,
                 paired_gain_vs_signed=gain,high_signal_model_gate=high_gate,noise_gate=noise_gate,baseline_max_abs_change_pC=drift,
                 source_noise_gate=source['source_noise_gate'],
                 waveform_response_gate=bool(high_gate and noise_gate and gain['gain_lo']>0 and drift<cfg['gates']['constant_baseline_max_delta_pC']),
                 regular_nominal_signal_median_pC=float(np.median(target[common&regular])),
                 saved_nonfinite_present=int((~np.isfinite(d['integral'])&present).sum()),saturated_modules=int(((d['status']&4)!=0).sum()),
                 extraction_resources=resources,neutrino_energy_gain='not measured',full_Athena_production_repair='not measured',
                 wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    d.update(cases_json=np.array(json.dumps(cases)),common_waveform=common,nominal_window_charge_pC=target)
    for prefix,values in [('readout',estimates),('model_readout',models),('offpulse',offpulse),('time_shift',times_fit)]:
        for name,value in values.items():d[prefix+'_'+name]=value
    np.savez_compressed(cache/'response.npz',**d)
    with np.load(cache/'response.npz') as saved:
        for key,value in d.items():np.testing.assert_array_equal(saved[key],value)
    summary.update(cache_bytes=(cache/'response.npz').stat().st_size,all_fields_readback_equal=True)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    unique={}
    for r in schemas:
        entry=unique.setdefault(r['class_name'],dict(class_name=r['class_name'],loaded_checksum=r['loaded_checksum'],saved_checksums=r['saved_checksums'],checked_branches=[]))
        assert entry['loaded_checksum']==r['loaded_checksum'];entry['checked_branches'].append(dict(file=r['file'],branch=r['branch']))
    (out/'native_schema_checks.json').write_text(json.dumps(list(unique.values()),indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='extraction_resources'}))


if __name__=='__main__':main()
