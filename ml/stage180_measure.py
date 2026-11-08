"""Batch-only real ordinary-Ecal paired support, no detector calibration claim."""
import csv
import gzip
import json
import math
import resource
import statistics
import sys
import time
from pathlib import Path
import numpy as np
import uproot
ROOT=Path.cwd();OUT=ROOT/'workbook/stage180_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage180'
p=json.loads((OUT/'protocol.json').read_text());phase=sys.argv[1]
assert phase in ['pilot','full','audit']
conditions=json.loads((ROOT/p['condition_input']).read_text())
mapping=next(r['rows'] for r in conditions if r['folder']=='/WAVE/DAQ/CableMapping' and r['run']==15838)
by_type={kind:sorted([r for r in mapping if r['payload']['type']==kind],key=lambda r:r['channel']) for kind in ['calo','calo2']}
pairs=[]
for i,lo in enumerate(by_type['calo']):
    key=lambda r:tuple(r['payload'][k] for k in ['station','plate','row','module'])
    matches=[(j,hi) for j,hi in enumerate(by_type['calo2']) if key(hi)==key(lo)]
    assert len(matches)==1 and lo['payload']['pmt']==0 and matches[0][1]['payload']['pmt']==1
    j,hi=matches[0];pairs.append(dict(module_key=list(key(lo)),Lo_index=i,Hi_index=j,Lo_channel=lo['channel'],Hi_channel=hi['channel']))
assert len(pairs)==4
labels=[f'Calo{gain}{j}' for gain in ['Lo','Hi'] for j in range(4)]
fields=['raw_charge','raw_peak','baseline_rms','status'];branches=['run','eventID']+[label+'_'+field for label in labels for field in fields]
tick=time.perf_counter();cpu=time.process_time();loops=[]
with uproot.open(p['PHYS'],array_cache=None,num_workers=4) as file:
    tree=file['nt'];N=tree.num_entries;assert set(branches)<=set(tree.keys())
    if phase=='pilot':
        parts=[]
        for start in [0,4096]:
            c=time.process_time();parts.append(tree.arrays(branches,entry_start=start,entry_stop=start+4096,library='np'))
            loops.append(time.process_time()-c)
        data={k:np.concatenate([r[k] for r in parts]) for k in branches}
    else:
        c=time.process_time();data=tree.arrays(branches,library='np');loops=[time.process_time()-c]
    read_bytes=int(file.file.source.num_requested_bytes)
assert np.all(data['run']==15838)
prefix={k:v[:8192] for k,v in data.items()}
if phase=='pilot':np.savez_compressed(CACHE/'pilot.npz',**prefix)
else:
    with np.load(CACHE/'pilot.npz') as old:
        for k,v in prefix.items():np.testing.assert_array_equal(v,old[k])
with gzip.open(ROOT/p['control_input'],'rt') as stream:capsule=json.load(stream)
control=json.loads(capsule['ntuples/energy_ml_stage161/pilot_raw.json.gz'])
comparisons=0
for parent in control:
    i=parent['PHYS_entry'];assert int(data['eventID'][i])==parent['event']
    for wave in parent['waves']:
        if wave['secondary'] or wave['detector'] not in ['Calo','Calo2']:continue
        detector='calo' if wave['detector']=='Calo' else 'calo2'
        ordered=by_type[detector];j=next(i for i,r in enumerate(ordered) if r['channel']==wave['channel'])
        label=('CaloLo' if detector=='calo' else 'CaloHi')+str(j)
        for field,key in [('raw_charge','raw_charge_pC'),('raw_peak','raw_peak_mV'),('baseline_rms','baseline_rms_mV'),('status','status')]:
            assert np.float32(data[label+'_'+field][i])==np.float32(wave[key]),(i,label,field)
            comparisons+=1
assert comparisons==128
records=[];binrows=[];fit=[]
entry=np.arange(len(data['run']));even=entry%2==0
for pair in pairs:
    lo='CaloLo'+str(pair['Lo_index']);hi='CaloHi'+str(pair['Hi_index'])
    qlo=data[lo+'_raw_charge'].astype(float);qhi=data[hi+'_raw_charge'].astype(float)
    slo=data[lo+'_status'];shi=data[hi+'_status'];plo=data[lo+'_raw_peak'].astype(float);phi=data[hi+'_raw_peak'].astype(float)
    rlo=data[lo+'_baseline_rms'].astype(float);rhi=data[hi+'_baseline_rms'].astype(float)
    finite=np.isfinite(qlo)&np.isfinite(qhi)&np.isfinite(plo)&np.isfinite(phi)&np.isfinite(rlo)&np.isfinite(rhi)
    # Negative signed Q is counted, never generically cleaned; positive Q is needed only for this log-ratio control.
    valid=finite&(slo==0)&(shi==0)&(qlo>0)&(qhi>0)&(rlo>0)&(rhi>0)&(plo>=10*rlo)&(phi>=10*rhi)
    ratio=np.full(len(valid),np.nan);ratio[valid]=np.log(qhi[valid]/qlo[valid])
    train=valid&even;held=valid&~even
    # Pilot only support/timing; never choose a fit or threshold from it.
    offset=float(np.median(ratio[train])) if phase!='pilot' and train.sum()>=100 else None
    residual=np.exp(ratio[held]-offset)-1 if offset is not None else np.array([])
    fit.append(dict(module=pair['Lo_index'],fit_even_N=int(train.sum()),validation_odd_N=int(held.sum()),
        relative_Hi_over_Lo_scale=float(np.exp(offset)) if offset is not None else None,
        validation_relative_residual_quantiles=np.quantile(residual,[.025,.5,.975]).tolist() if len(residual) else None))
    records.append(dict(module=pair['Lo_index'],N=len(valid),finite_N=int(finite.sum()),Lo_status0_N=int((slo==0).sum()),Hi_status0_N=int((shi==0).sum()),
        paired_status0_N=int(((slo==0)&(shi==0)).sum()),positive_highSNR_overlap_N=int(valid.sum()),
        Lo_nonzero_Hi_good_highSNR_N=int(((slo!=0)&(shi==0)&np.isfinite(qhi)&(qhi>0)&(rhi>0)&(phi>=10*rhi)).sum()),
        negative_raw_measurements_N=int((qlo<0).sum()+(qhi<0).sum()),explicit_minus999_N=int((qlo==-999).sum()+(qhi==-999).sum()),
        max_Lo_raw_peak_mV=float(plo[np.isfinite(plo)].max()),max_Hi_raw_peak_mV=float(phi[np.isfinite(phi)].max())))
    for lower,upper in zip(p['bins_raw_peak_mV'][:-1],p['bins_raw_peak_mV'][1:]):
        use=valid&(plo>=lower)&(plo<upper);test=use&~even
        res=np.exp(ratio[test]-offset)-1 if offset is not None else np.array([])
        binrows.append(dict(module=pair['Lo_index'],Lo_peak_lower_mV=lower,Lo_peak_upper_mV=upper,
            overlap_N=int(use.sum()),validation_N=int(test.sum()),
            validation_median_relative_residual=float(np.median(res)) if len(res) else None,
            validation_abs95_relative_residual=float(np.quantile(np.abs(res),.95)) if len(res) else None))
for name,rows in [(f'{phase}_support.tsv',records),(f'{phase}_amplitude_bins.tsv',binrows)]:
    with (OUT/name).open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n',quoting=csv.QUOTE_NONNUMERIC);writer.writeheader();writer.writerows(rows)
summary=dict(passed=True,phase=phase,N=len(data['run']),source_N=N,pairs=pairs,native4_scalar_comparisons=comparisons,
    prefix8192_exact=True if phase!='pilot' else None,measure_CPU_s=time.process_time()-cpu,
    loop_CPU_s=loops,startup_and_postprocess_CPU_s=time.process_time()-cpu-sum(loops),wall_s=time.perf_counter()-tick,
    ROOT_read_bytes=read_bytes,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    support=records,relative_fits=fit,absolute_amplitude_reference=False,target_MC_second_readout_available=False,
    interpretation='Same-module real dual-readout support and conditional proportionality only; no absolute energy/PMT linearity/high-amplitude precision or ν improvement certification.',overall_complete=False)
(OUT/f'{phase}_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary,flush=True)
if phase=='audit':
    full=json.loads((OUT/'full_summary.json').read_text())
    assert summary['support']==full['support'] and summary['relative_fits']==full['relative_fits'] and summary['pairs']==full['pairs']
    scalar_checks=[]
    for pair in pairs:
        lo='CaloLo'+str(pair['Lo_index']);hi='CaloHi'+str(pair['Hi_index'])
        selected=[]
        for i,v in enumerate(zip(data[lo+'_raw_charge'],data[hi+'_raw_charge'],data[lo+'_raw_peak'],data[hi+'_raw_peak'],
            data[lo+'_baseline_rms'],data[hi+'_baseline_rms'],data[lo+'_status'],data[hi+'_status'])):
            ql,qh,pl,ph,rl,rh,sl,sh=map(float,v)
            if sl==0 and sh==0 and all(math.isfinite(x) for x in [ql,qh,pl,ph,rl,rh]) and min(ql,qh,rl,rh)>0 and pl>=10*rl and ph>=10*rh:
                selected.append((i,math.log(qh/ql)))
        expected=full['relative_fits'][pair['Lo_index']]
        fit_values=[v for i,v in selected if i%2==0];val_values=[v for i,v in selected if i%2==1]
        assert len(selected)==full['support'][pair['Lo_index']]['positive_highSNR_overlap_N']
        assert len(fit_values)==expected['fit_even_N'] and len(val_values)==expected['validation_odd_N']
        if len(fit_values)>=100:
            scale=math.exp(statistics.median(fit_values))
            assert abs(scale-expected['relative_Hi_over_Lo_scale'])<1e-12*max(1,abs(scale))
        scalar_checks.append(dict(module=pair['Lo_index'],overlap_N=len(selected),fit_N=len(fit_values),validation_N=len(val_values),passed=True))
    (OUT/'independent_validation.json').write_text(json.dumps(dict(passed=True,actual_full_reread_N=len(data['run']),
        native4_scalar_comparisons=comparisons,full_counts_and_fixed_relative_fits_exact=True,independent_scalar_checks=scalar_checks),indent=2)+'\n')
