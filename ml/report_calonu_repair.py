#!/usr/bin/env python3
"""Collect frozen confirmation and compare numerical repair with fixed waveform readouts."""
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np

from calonu_weak_readout import evaluate, template_weights
from report_calonu_native import table


def main():
    tick,cpu=time.perf_counter(),time.process_time()
    repo=Path(__file__).resolve().parents[1]
    out=repo/'workbook/stage38_energy_ml'; cache=repo/'ntuples/energy_ml_stage38'
    cfg=json.loads((repo/'ml/configs/calonu_repair_control.json').read_text())
    groups=cfg['groups']; arrays={}; cases=[]; extraction=[]; schema=[]; replay=[]; replay_summary=[]
    for group in groups:
        with np.load(cache/f'shards/{group}.npz') as z:
            data={k:z[k] for k in z.files}
        cases.extend(json.loads(str(data.pop('cases_json'))))
        extraction.append(json.loads(str(data.pop('metadata_json'))))
        schema.extend(json.loads(str(data.pop('schemas_json'))))
        for k,v in data.items(): arrays.setdefault(k,[]).append(v)
        replay.extend(csv.DictReader((cache/f'shards/{group}_replay.tsv').open(),delimiter='\t'))
        replay_summary.append(json.loads((cache/f'shards/{group}_summary.json').read_text()))
    d={k:np.concatenate(v) for k,v in arrays.items()}
    assert len(cases)==128 and len(replay)==512 and np.all(d['saved_samples']==76)
    assert len({(r['index'],r['input_entry']) for r in cases})==128
    assert set(r['index'] for r in cases).isdisjoint([0,5,6,11])
    expected_ids=np.array([3892314112,3758096384,4160749568,4026531840],np.uint32)
    assert np.all(d['id32']==expected_ids)
    d['cases_json']=np.array(json.dumps(cases))
    # Check every module against stage36, rather than trusting run/event IDs which repeat in PG.
    with np.load(repo/'ntuples/energy_ml_stage36/MC.npz') as z:
        old={k:z[k] for k in z.files}
    lookup={(int(g),int(s)):i for i,(g,s) in enumerate(zip(old['group_index'],old['source_selected_row']))}
    max_cache_difference=0.
    for j,c in enumerate(cases):
        k=lookup[c['index'],c['selected_row']]
        for i in range(4):
            assert int(d['status'][j,i])==int(old[f'CaloNu{i}_status'][k])
            for source,field in [('raw_integral','raw_charge'),('integral','charge')]:
                value=d[source][j,i]/50; reference=old[f'CaloNu{i}_{field}'][k]
                if np.isfinite(value) and np.isfinite(reference):
                    max_cache_difference=max(max_cache_difference,float(abs(value-reference)))
                    assert np.isclose(value,reference,rtol=3e-6,atol=3e-5)
                else: assert value==reference or (np.isnan(value) and np.isnan(reference))
    samples=(d['saved_time']/2).astype(int)
    assert np.all(d['saved_time']==d['saved_time'][:,:1,:]), 'Shared template requires equal channel windows'
    wave=(d['baseline_mean'][:,:,None]-np.take_along_axis(d['adc'],samples,axis=2)*(2/16.384)).astype(np.float32)
    np.testing.assert_array_equal(wave,d['saved_wave'])
    raw=np.maximum(wave,0).sum(axis=2,dtype=float)*2/50
    np.testing.assert_allclose(raw,d['raw_integral']/50,rtol=0,atol=3e-5)
    target=[]; p=[]; role=[]; gid=[]; estimates={}; offpulse={}; shifted={}; model_estimates={}
    patched=np.empty((128,4)); original=np.empty((128,4)); repair_index={(int(r['group']),int(r['input_entry']),int(r['branch'])):r for r in replay}
    for j,c in enumerate(cases):
        model=np.take_along_axis(d['signal_nominal_ADC'][j],samples[j],axis=1)*(2/16.384)
        qtrue=model.sum()*2/50
        target.append(qtrue);p.append(c['fingerprint']['Track_p0']/1000);role.append(c['role']);gid.append(groups.index(c['index']))
        output=evaluate(wave[j],d['adc'][j],d['baseline_mean'][j],d['baseline_rms'][j],d['saved_time'][j,0],cfg['template_parameters'])
        model_adc=d['signal_nominal_ADC'][j]
        model_output=evaluate(model, -model_adc, np.zeros(4),np.zeros(4),d['saved_time'][j,0],cfg['template_parameters'])
        for name,r in output.items():
            estimates.setdefault(name,[]).append(r['charge'].sum())
            offpulse.setdefault(name,[]).append(r['offpulse'].sum())
            shifted.setdefault(name,[]).append([r['shifted_minus'].sum(),r['shifted_plus'].sum()])
            model_estimates.setdefault(name,[]).append(model_output[name]['charge'].sum())
        for i in range(4):
            r=repair_index[c['index'],c['input_entry'],i]
            patched[j,i]=float(r['repaired_integral_mVns'])/50
            original[j,i]=float(r['original_integral_mVns'])/50
    target=np.array(target);p=np.array(p);gid=np.array(gid);role=np.array(role)
    estimates={k:np.array(v) for k,v in estimates.items()}
    estimates['source_repaired_fit']=patched.sum(axis=1)
    assert all(np.isfinite(v).all() for v in estimates.values())
    rng=np.random.default_rng(cfg['bootstrap_seed']);draws=np.zeros((cfg['bootstrap_replicates'],4),int)
    for cols in [[0,1],[2,3]]: draws[:,cols]=rng.multinomial(2,[.5,.5],size=len(draws))
    subsets=[('regular',role=='regular'),('regular_p100_250',(role=='regular')&(p<250)),
             ('regular_p250_1000',(role=='regular')&(p>=250)),('diagnostic',role!='regular')]
    metrics=[]; paired=[]; baselines=[]
    for subset,mask in subsets:
        weight=draws[:,gid[mask]]; denominator=weight.sum(axis=1)
        reference=estimates['signed_saved'][mask]-target[mask]
        ref_rms=np.sqrt(np.average(reference**2));ref_boot=np.sqrt(weight@(reference**2)/denominator)
        for name,y in estimates.items():
            error=y[mask]-target[mask]
            boot=np.sqrt(weight@(error**2)/denominator)
            metric=dict(subset=subset,method=name,N=int(mask.sum()),rmse_pC=float(np.sqrt(np.mean(error**2))),
                        bias_pC=float(error.mean()),median_error_pC=float(np.median(error)),
                        R68_pC=float((np.quantile(error,.84)-np.quantile(error,.16))/2),
                        tail_abs_gt025=float(np.mean(abs(error)>.25)),tail_abs_gt1=float(np.mean(abs(error)>1)),
                        rmse_lo_pC=float(np.quantile(boot,.025)) if subset!='diagnostic' else 'not_applicable',
                        rmse_hi_pC=float(np.quantile(boot,.975)) if subset!='diagnostic' else 'not_applicable',
                        bias_lo_pC=float(np.quantile(weight@error/denominator,.025)) if subset!='diagnostic' else 'not_applicable',
                        bias_hi_pC=float(np.quantile(weight@error/denominator,.975)) if subset!='diagnostic' else 'not_applicable',
                        offpulse_rms_pC=float(np.sqrt(np.mean(np.array(offpulse[name])[mask]**2))) if name in offpulse else 'not_applicable',
                        offpulse_bias_pC=float(np.mean(np.array(offpulse[name])[mask])) if name in offpulse else 'not_applicable',
                        no_noise_model_bias_pC=float(np.mean(np.array(model_estimates[name])[mask]-target[mask])) if name in model_estimates else 'not_applicable')
            metrics.append(metric)
            if subset!='diagnostic':
                gain=1-boot/ref_boot
                paired.append(dict(subset=subset,method=name,reference='signed_saved',relative_RMSE_gain=1-metric['rmse_pC']/ref_rms,
                                   gain_lo=float(np.quantile(gain,.025)),gain_hi=float(np.quantile(gain,.975))))
            if name in shifted:
                delta=np.array(shifted[name])[mask]-y[mask,None]
                baselines.append(dict(subset=subset,method=name,minus_sigma_median_shift_pC=float(np.median(delta[:,0])),
                                      plus_sigma_median_shift_pC=float(np.median(delta[:,1])),max_abs_shift_pC=float(abs(delta).max())))
    event_rows=[]
    for j,c in enumerate(cases):
        event_rows.append(dict(group=c['index'],input_entry=c['input_entry'],selected_row=c['selected_row'],role=c['role'],
                               reco_p_GeV=p[j],nominal_signal_pC=target[j],sensitive_hit_energy_MeV=float(d['hit_energy_MeV'][j].sum()),
                               **{name+'_pC':float(v[j]) for name,v in estimates.items()}))
    table(out/'readout_metrics.tsv',metrics);table(out/'paired_readout_gain.tsv',paired)
    table(out/'baseline_sensitivity.tsv',baselines);table(out/'confirmation_events.tsv',event_rows)
    table(out/'confirmation_replay.tsv',replay)
    d['repaired_fit_charge_pC']=patched
    np.savez_compressed(cache/'confirmation.npz',**d)
    with np.load(cache/'confirmation.npz') as z:
        for k,v in d.items(): np.testing.assert_array_equal(z[k],v)
    # Preservation uses only saved quality/parameters, never the repaired outcome.
    normal=[r for j,c in enumerate(cases) for i in range(4)
            for r in [repair_index[c['index'],c['input_entry'],i]]
            if int(r['saved_status'])==0 and float(r['saved_integral_mVns'])>0
            and np.isfinite(float(r['saved_integral_mVns'])) and d['width'][j,i]>=1]
    preserved=[r for r in normal if np.isclose(float(r['fixed_saved_parameter_integral_mVns']),float(r['saved_integral_mVns']),rtol=3e-6,atol=1e-5)]
    chosen=next(r for r in paired if r['subset']=='regular' and r['method']==cfg['primary_readout'])
    primary=next(r for r in metrics if r['subset']=='regular' and r['method']==cfg['primary_readout'])
    ref=next(r for r in metrics if r['subset']=='regular' and r['method']=='signed_saved')
    drift=next(r for r in baselines if r['subset']=='regular' and r['method']==cfg['primary_readout'])
    summary=dict(events=128,regular=int((role=='regular').sum()),diagnostic=int((role!='regular').sum()),groups=groups,
                 ADC_waveform_exact=True,cache_charge_max_difference_pC=max_cache_difference,
                 original_nonfinite_modules=int((~np.isfinite(original)).sum()),repaired_nonfinite_modules=int((~np.isfinite(patched)).sum()),
                 saturated_saved_modules=int(((d['status']&4)!=0).sum()),narrow_saved_valid_modules=int(((d['width']<.2)&((d['status']&49)==0)).sum()),
                 positive_resolved_saved_fixed_parameter_checks=len(normal),positive_resolved_preserved=len(preserved),
                 primary_gain=chosen,offpulse_RMS_primary_pC=primary['offpulse_rms_pC'],offpulse_RMS_signed_pC=ref['offpulse_rms_pC'],
                 baseline_max_abs_shift_pC=drift['max_abs_shift_pC'],
                 gate_passed=chosen['gain_lo']>0 and primary['offpulse_rms_pC']<ref['offpulse_rms_pC'] and drift['max_abs_shift_pC']<1e-10,
                 final_cache_bytes=(cache/'confirmation.npz').stat().st_size,all_field_readback_equal=True,
                 extraction_resources=extraction,replay_resources=replay_summary,
                 wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                 peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                 data_MC_physics_closure='not measured',neutrino_energy_gain='not measured')
    (out/'confirmation_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    # Repeated persistent classes need only one copy of their layout values plus the checked paths.
    unique={}
    for r in schema:
        key=r['class_name'];u=unique.setdefault(key,dict(class_name=key,loaded_checksum=r['loaded_checksum'],
                    saved_checksums=r['saved_checksums'],checked_branches=[]))
        assert u['loaded_checksum']==r['loaded_checksum']
        u['checked_branches'].append(dict(file=r['file'],branch=r['branch']))
    (out/'native_schema_checks.json').write_text(json.dumps(list(unique.values()),indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['extraction_resources','replay_resources']}))


if __name__=='__main__': main()
