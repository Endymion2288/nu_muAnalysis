"""Batch-only fixed strict-time check for real ordinary-Ecal dual-range response."""
import csv,gzip,json,math,resource,statistics,sys,time
from pathlib import Path
import numpy as np
import uproot
ROOT=Path.cwd();OUT=ROOT/'workbook/stage181_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage181'
p=json.loads((OUT/'protocol.json').read_text());old=json.loads((ROOT/p['relative_input']).read_text());phase=sys.argv[1]
labels=[f'Calo{gain}{j}' for gain in ['Lo','Hi'] for j in range(4)]
fields=['raw_charge','raw_peak','baseline_rms','status','localtime','bcidtime']
branches=['run','eventID']+[label+'_'+field for label in labels for field in fields]
tick=time.perf_counter();cpu=time.process_time();loops=[]
with uproot.open(p['PHYS'],array_cache=None,num_workers=4) as file:
    tree=file['nt'];N=tree.num_entries;missing=sorted(set(branches)-set(tree.keys()))
    if missing:
        (OUT/f'{phase}_summary.json').write_text(json.dumps(dict(passed=False,missing_branches=missing,terminal_support_result=True),indent=2)+'\n')
        raise SystemExit('Required time fields unsupported; no substitution')
    if phase=='pilot':
        parts=[]
        for start in [0,4096]:
            c=time.process_time();parts.append(tree.arrays(branches,entry_start=start,entry_stop=start+4096,library='np'));loops.append(time.process_time()-c)
        data={k:np.concatenate([r[k] for r in parts]) for k in branches}
    else:
        c=time.process_time();data=tree.arrays(branches,library='np');loops=[time.process_time()-c]
    readbytes=int(file.file.source.num_requested_bytes)
assert np.all(data['run']==15838)
if phase=='pilot':np.savez_compressed(CACHE/'pilot.npz',**data)
else:
    with np.load(CACHE/'pilot.npz') as z:
        for k in branches:np.testing.assert_array_equal(data[k][:8192],z[k])
with gzip.open(ROOT/p['control_input'],'rt') as stream:capsule=json.load(stream)
native=json.loads(capsule['ntuples/energy_ml_stage161/pilot_raw.json.gz']);raw_checks=time_checks=0
for event in native:
    i=event['PHYS_entry'];assert event['event']==int(data['eventID'][i])
    for wave in event['waves']:
        if wave['secondary'] or wave['detector'] not in ['Calo','Calo2']:continue
        channel=wave['channel'];label=('CaloLo' if channel<16 else 'CaloHi')+str(channel if channel<16 else channel-16)
        for field,key in [('raw_charge','raw_charge_pC'),('raw_peak','raw_peak_mV'),('baseline_rms','baseline_rms_mV'),('status','status')]:
            assert np.float32(data[label+'_'+field][i])==np.float32(wave[key]);raw_checks+=1
        if wave['status']==0:
            assert np.float32(data[label+'_localtime'][i])==np.float32(wave['localtime_ns']);time_checks+=1
assert raw_checks==128
even=np.arange(len(data['run']))%2==0;support=[];rows=[];offsets=[];scalar=[]
for j in range(4):
    lo='CaloLo'+str(j);hi='CaloHi'+str(j)
    v=lambda label,field:data[label+'_'+field].astype(float)
    ql,qh=v(lo,'raw_charge'),v(hi,'raw_charge');pl,ph=v(lo,'raw_peak'),v(hi,'raw_peak');rl,rh=v(lo,'baseline_rms'),v(hi,'baseline_rms')
    base=(v(lo,'status')==0)&(v(hi,'status')==0)&np.isfinite(ql)&np.isfinite(qh)&np.isfinite(pl)&np.isfinite(ph)&np.isfinite(rl)&np.isfinite(rh)&(ql>0)&(qh>0)&(rl>0)&(rh>0)&(pl>=10*rl)&(ph>=10*rh)
    qres=np.full(len(base),np.nan);qres[base]=(qh[base]/ql[base])/old['relative_fits'][j]['relative_Hi_over_Lo_scale']-1
    lt,ht=v(lo,'localtime'),v(hi,'localtime');lb,hb=v(lo,'bcidtime'),v(hi,'bcidtime')
    strict=base&np.isfinite(lt)&np.isfinite(ht)&(lt>0)&(ht>0)&np.isfinite(lb)&np.isfinite(hb)&(lb!=-999)&(hb!=-999)
    # Missing time does not remove charge-control rows from the original denominator.
    support.append(dict(module=j,N=len(base),original_charge_overlap_N=int(base.sum()),strict_time_N=int(strict.sum()),unknown_time_on_charge_overlap_N=int((base&~strict).sum())))
    for name,difference in [('local',ht-lt),('bcid',hb-lb)]:
        train=strict&even;held=strict&~even
        offset=float(np.median(difference[train])) if train.sum()>=100 and phase!='pilot' else None
        offsets.append(dict(module=j,definition=name,fit_N=int(train.sum()),heldout_N=int(held.sum()),offset_ns=offset,
            heldout_abs95_ns=float(np.quantile(np.abs(difference[held]-offset),.95)) if offset is not None and held.any() else None))
        if phase=='audit' and offset is not None:
            values=[float(difference[i]) for i in np.flatnonzero(train)]
            assert abs(statistics.median(values)-offset)<1e-12
            scalar.append(dict(module=j,definition=name,independent_median_exact=True,N=len(values)))
        for lower,upper in zip(p['bins_raw_peak_mV'][:-1],p['bins_raw_peak_mV'][1:]):
            selected=held&(pl>=lower)&(pl<upper)
            for kind in ['all','within2ns','outside2ns']:
                use=selected.copy()
                if kind!='all':use &= (np.abs(difference-offset)<=2) if offset is not None and kind=='within2ns' else (np.abs(difference-offset)>2) if offset is not None else False
                q=qres[use];t=difference[use]-offset if offset is not None else np.array([])
                rows.append(dict(module=j,definition=name,Lo_peak_lower_mV=lower,Lo_peak_upper_mV=upper,group=kind,N=int(use.sum()),
                    median_charge_ratio_residual=float(np.median(q)) if len(q) else None,
                    abs95_charge_ratio_residual=float(np.quantile(np.abs(q),.95)) if len(q) else None,
                    median_time_residual_ns=float(np.median(t)) if len(t) else None,
                    abs95_time_residual_ns=float(np.quantile(np.abs(t),.95)) if len(t) else None))
with (OUT/f'{phase}_diagnostics.tsv').open('w') as stream:
    w=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n',quoting=csv.QUOTE_NONNUMERIC);w.writeheader();w.writerows(rows)
r=dict(passed=True,phase=phase,N=len(data['run']),source_N=N,loop_CPU_s=loops,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
    ROOT_read_bytes=readbytes,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,original_native128_exact=True,
    native_status0_localtime_checks=time_checks,prefix8192_exact=phase!='pilot',support=support,offsets=offsets,original_Q_scales_frozen=True,
    no_bad_hit_timing=True,overall_complete=False)
(OUT/f'{phase}_summary.json').write_text(json.dumps(r,indent=2)+'\n');print(r,flush=True)
if phase=='audit':
    full=json.loads((OUT/'full_summary.json').read_text())
    assert r['support']==full['support'] and r['offsets']==full['offsets']
    assert (OUT/'audit_diagnostics.tsv').read_bytes()==(OUT/'full_diagnostics.tsv').read_bytes()
    (OUT/'independent_validation.json').write_text(json.dumps(dict(passed=True,full_read_N=len(data['run']),scalar_medians=scalar,
        diagnostics_exact=True,original_native128_exact=True,native_localtime_N=time_checks),indent=2)+'\n')
