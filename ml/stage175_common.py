"""Exact selected-entry PHYS reads and strict calibrated means; batch workers only."""
import json,resource,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage175_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage175'
NAMES=['Timing0','Timing1','Timing2','Timing3','Veto21']
TRACK=['Track_pz0','Track_X_atTrig','Track_Y_atTrig','Track_ThetaX_atTrig','Track_ThetaY_atTrig']
OPTIONAL=['Track_x0','Track_y0','Track_z0']
def write(name,obj): (OUT/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def plan():return json.loads((OUT/'protocol.json').read_text())
def sources():return json.loads((ROOT/plan()['source_contract']).read_text())['requests']
def read(task):
    import ROOT as R
    index,phase=task;tick=time.perf_counter();cpu=time.process_time();b0=int(R.TFile.GetFileBytesRead());s=sources()[index]
    cases=s['cases']
    if phase in ['pilot','profile']:cases=[c for c in cases if c['role']==1][:32]
    if phase=='audit':cases=cases[:1]
    n=len(cases)
    d=dict(row=np.array([c['row'] for c in cases]),entry=np.array([c['entry'] for c in cases]),run=np.array([c['run'] for c in cases]),event=np.array([c['event'] for c in cases]),role=np.array([c['role'] for c in cases]),
        present=np.zeros(n,bool),mapping=np.zeros(n,bool),track_match=np.zeros(n,bool),status=np.full((n,5),-999),rawQ_pC=np.full((n,5),np.nan),localtime_ns=np.full((n,5),np.nan),
        track=np.full((n,5),np.nan),s0_xyz_mm=np.full((n,3),np.nan))
    required=['run','eventID']+TRACK+[s+'_'+v for s in NAMES for v in ['status','raw_charge','localtime']]
    report=dict(index=index,phase=phase,source=s['phys'],N=n,schema_supported=False,missing=[],S0_missing=[],histogram_mapping=False)
    loop_cpu=0.;first_entry_cpu=0.
    if s['phys']:
        f=R.TFile.Open(s['phys']);assert f and not f.IsZombie(),s['phys'];t=f.Get('nt');assert t
        schema={b.GetName() for b in t.GetListOfBranches()};missing=sorted(set(required)-schema);optional=[b for b in OPTIONAL if b in schema]
        report.update(missing=missing,S0_missing=sorted(set(OPTIONAL)-schema),schema_supported=not missing)
        hist=all(f.Get(f'hRandomCharge{8+j}') and str(f.Get(f'hRandomCharge{8+j}').GetTitle()).startswith(f'Timing{j} Ch{8+j} ') for j in range(4))
        mapping=next(r['supported'] for r in json.loads((OUT/'cable_mapping.json').read_text()) if r['run']==s['run']) and hist
        report['histogram_mapping']=bool(hist)
        if not missing:
            t.SetBranchStatus('*',0)
            for b in required+optional:t.SetBranchStatus(b,1)
            for k,c in enumerate(cases):
                entry_cpu=time.process_time()
                assert t.GetEntry(c['entry'])>0
                assert (int(t.run),int(t.eventID))==(c['run'],c['event'])
                d['present'][k]=True;d['mapping'][k]=mapping
                for j,name in enumerate(NAMES):
                    d['status'][k,j]=int(getattr(t,name+'_status'));d['rawQ_pC'][k,j]=float(getattr(t,name+'_raw_charge'));d['localtime_ns'][k,j]=float(getattr(t,name+'_localtime'))
                pz=list(t.Track_pz0);lead=int(np.argmax(pz)) if pz else None
                matched=lead is not None and np.isclose(pz[lead]/1000,c['pz'],rtol=3e-7,atol=3e-5)
                d['track_match'][k]=matched
                if matched:
                    d['track'][k]=[float(getattr(t,b)[lead]) for b in TRACK]
                    for j,b in enumerate(OPTIONAL):
                        if b in optional:d['s0_xyz_mm'][k,j]=float(getattr(t,b)[lead])
                elapsed=time.process_time()-entry_cpu
                if k==0:first_entry_cpu+=elapsed
                else:loop_cpu+=elapsed
        f.Close()
    np.savez_compressed(CACHE/f'{phase}_{index}.npz',**d)
    report.update(present_N=int(d['present'].sum()),leading_match_N=int(d['track_match'].sum()),strict_end_N=((d['status']==0)&np.isfinite(d['localtime_ns'])&(d['localtime_ns']>0)&d['present'][:,None]).sum(0).tolist(),
        negative_rawQ_N=int((d['rawQ_pC']<0).sum()),minus999_rawQ_N=int((d['rawQ_pC']==-999).sum()),S0_finite_N=int(np.isfinite(d['s0_xyz_mm']).all(1).sum()),
        ROOT_read_bytes=int(R.TFile.GetFileBytesRead())-b0,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        output_bytes=(CACHE/f'{phase}_{index}.npz').stat().st_size,first_entry_CPU_s=first_entry_cpu,subsequent_loop_CPU_s=loop_cpu)
    write(f'{phase}_{index}_summary.json',report);return report

def means(d):
    records=json.loads((ROOT/'workbook/stage174_energy_ml/calibrations.json').read_text())
    time=d['localtime_ns'];q=d['rawQ_pC'];track=d['track'];n=len(track)
    strict=(d['status']==0)&np.isfinite(time)&(time>0)&d['present'][:,None]
    projection=np.isfinite(track).all(1)&(abs(track[:,1])<1000)&(abs(track[:,2])<1000)&(abs(track[:,3])<1)&(abs(track[:,4])<1)&d['track_match']
    value=np.full((n,2),np.nan);flags=np.zeros((n,4),bool)
    for col,(i,j) in enumerate([(0,1),(2,3)]):
        mc=next(r for r in records if r['label']=='MC100012' and r['pair']==[i,j] and r['kind']=='relative_mean')
        real=next(r for r in records if r['label']=='data8006' and r['pair']==[i,j] and r['kind']=='relative_mean')
        base=strict[:,i]&strict[:,j]&strict[:,4];use=base&projection&d['mapping']&np.isfinite(q[:,[i,j,4]]).all(1)&(q[:,[i,j,4]]>0).all(1)
        if not(mc['usable'] and real['usable']):use &= False
        for k,v in [('qL_pC',q[:,i]),('qR_pC',q[:,j]),('qRef_pC',q[:,4]),('x_mm',track[:,1]),('y_mm',track[:,2])]:
            lo,hi=mc['training_ranges'][k];use &= (v>=lo)&(v<=hi)
        u=np.flatnonzero(use)
        if len(u):
            D=np.column_stack([np.ones(len(u)),1/np.sqrt(q[u,i]),1/np.sqrt(q[u,j]),1/np.sqrt(q[u,4])])
            path=1598.9*(np.sqrt(1+np.tan(track[u,3])**2+np.tan(track[u,4])**2)-1)/299.792458
            value[u,col]=(time[u,i]+time[u,j])/2-time[u,4]-path-D@np.asarray(mc['coefficient'])
        flags[:,2*col]=base;flags[:,2*col+1]=use
        assert not np.isfinite(value[~base,col]).any()
    return flags,value
