"""Collect successful stage80 phases and validate/merge the fixed scalar supplement."""
import argparse
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path
import numpy as np
from pulse_ablation import *


def main(mode):
    start=begin();submission=json.loads((OUT/(mode+'_submission.json')).read_text());cluster=submission['cluster']
    attrs='ClusterId,ProcId,JobStatus,ExitCode,NumJobStarts,RequestCpus,RequestMemory,MaxRuntime,RemoteWallClockTime,RemoteUserCpu,RemoteSysCpu,ResidentSetSize'
    h=json.loads(subprocess.check_output(['condor_history',str(cluster),'-limit','4','-json','-attributes',attrs],text=True))
    assert len(h)==4 and all(r['JobStatus']==4 and r['ExitCode']==0 and r['NumJobStarts']==1 for r in h)
    assert all(r['RequestCpus']==1 and r['RequestMemory']==3000 and r['MaxRuntime']==1800 for r in h)
    save(OUT/(mode+'_history.json'),h)
    transport_fallback=[]
    with tempfile.TemporaryDirectory(prefix='stage80_collect_') as td:
        for job in (range(4) if mode=='extract' else JOBS):
            path=CACHE/f'{mode}_{job}.tar.gz'
            if not path.exists():
                path=Path(td)/f'{mode}_{job}.tar.gz'
                subprocess.run(['xrdcp','--silent',f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage80/{mode}_{job}.tar.gz',str(path)],check=True)
                transport_fallback.append(dict(job=job,bytes=path.stat().st_size,reason='EOS FUSE negative metadata cache; retrieve existing successful output, no compute retry'))
            with tarfile.open(path) as t:
                for member in t.getmembers():
                    if member.isdir():continue
                    assert member.isfile() and '..' not in member.name and member.name.startswith(('workbook/stage80_energy_ml/','ntuples/energy_ml_stage80/','ml/artifacts/stage80/'))
                    destination=REPO/member.name;contents=t.extractfile(member).read()
                    if destination.exists():assert destination.read_bytes()==contents
                    else:destination.parent.mkdir(exist_ok=True,parents=True);destination.write_bytes(contents)
    save(OUT/(mode+'_transport.json'),dict(fallback=transport_fallback,no_compute_retries=True))
    if mode=='extract':
        parts=[arrays(CACHE/f'extract{j}.npz') for j in range(4)];shape={k:np.concatenate([a[k] for a in parts]) for k in parts[0]}
        order=np.argsort(shape['row']);shape={k:v[order] for k,v in shape.items()}
        identity=arrays(CACHE/'identity.npz');np.testing.assert_array_equal(shape['row'],identity['row'])
        assert len(np.unique(shape['row']))==63944
        np.testing.assert_array_equal(np.isnan(shape['shape']),np.repeat(~shape['valid'],2,axis=1))
        st=identity['status'].astype(int);good=(st&445)==0
        assert np.all(~shape['valid']|good)
        for j in range(11):
            use=shape['valid'][:,j];assert np.all(shape['shape'][use,2*j]>0) and np.all(shape['shape'][use,2*j+1]>0)
        old=arrays(REPO/'ntuples/energy_ml_stage79/measurements.npz');ix={int(r):i for i,r in enumerate(shape['row'])}
        positions=np.array([ix[int(r)] for r in old['row']]);valid=strong_shape_validity(old)
        oldshape=np.stack([old['raw_peak'],old['width']],axis=2).reshape(len(valid),22).astype('float32');oldshape[np.repeat(~valid,2,axis=1)]=np.nan
        np.testing.assert_array_equal(shape['shape'][positions],oldshape)
        np.savez_compressed(CACHE/'shape.npz',**shape);d=data();np.savez_compressed(CACHE/'input.npz',**d)
        from group_risk import inputs
        original=inputs()
        for key,value in original.items():np.testing.assert_array_equal(d[key],value)
        p=json.loads((OUT/'protocol.json').read_text());split=[]
        for job in JOBS:
            use,held,purge=training_split(d,p,job)
            split.append(dict(job=job,train_N=int(use.sum()),held_N=int(held.sum()) if held is not None else 0,purged_N=int(purge.sum())))
        save(OUT/'input_validation.json',dict(N=63944,original62_and_roles_exact=True,all_events_retained=True,
            stage79_same_event_shape_exact_N=len(positions),missing_N=[int(d['missing'][d['role']==r].sum()) for r in ['train','cal','eval']],
            strong_channel_N=int(shape['valid'].sum()),channel_N=int(shape['valid'].size),splits=split,
            input_bytes=(CACHE/'input.npz').stat().st_size,**resources(start)))
    print(json.dumps(dict(mode=mode,jobs=len(h),remote_CPU_s=sum(r['RemoteUserCpu']+r['RemoteSysCpu'] for r in h),
        remote_wall_sum_s=sum(r['RemoteWallClockTime'] for r in h),**resources(start))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['extract','fit']);a=p.parse_args();main(a.mode)
