"""Freeze after QA, test the actual package without fitting, submit each phase once."""
import argparse
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from pulse_ablation import *


def main(mode):
    start=begin();assert not (OUT/(mode+'_submission.json')).exists()
    audit=json.loads((OUT/'source_audit.json').read_text());qa=json.loads((OUT/'qa.json').read_text())
    assert audit['passed'] and audit['N']==254 and qa['N']==40 and qa['stage79_QA_exact']
    if mode=='extract':
        assert not (OUT/'protocol.json').exists()
        p=json.loads((OUT/'proposal.json').read_text());p.update(frozen_utc=stamp(),status='frozen after actual source and scalar QA',
            scalar_QA_requested_bytes=qa['requested_bytes'],scalar_QA_CPU_s=qa['CPU_s'],scalar_QA_wall_s=qa['wall_s'],
            source_audit_before_formal=True,CPU_soft_hard_s=[850,875],fit_callback_CPU_s=790,worker_timeout_s=1750)
        save(OUT/'protocol.json',p)
    else:assert (OUT/'input_validation.json').exists()
    paths=['ml/pulse_ablation.py','ml/pulse_information_audit.py','ml/audited_features.py','ml/track_response.py',
        'ml/support_augmentation.py','ml/group_risk.py','ml/expert_combination.py',f'ml/{"extract" if mode=="extract" else "fit"}_pulse_ablation.py',
        'workbook/stage80_energy_ml/protocol.json',f'ntuples/energy_ml_stage80/{"identity" if mode=="extract" else "input"}.npz']
    payload=REPO/f'software/energy-ml-pulse-ablation-stage80-{mode}.tar.gz';assert not payload.exists()
    with tarfile.open(payload,'w:gz',compresslevel=1) as t:
        for name in paths:t.add(REPO/name,arcname=name)
    checks=[];jobs=range(4) if mode=='extract' else JOBS
    with tempfile.TemporaryDirectory(prefix='stage80_package_') as td:
        with tarfile.open(payload) as t:t.extractall(td,filter='data')
        for job in jobs:
            command=[sys.executable,str(Path(td)/f'ml/{"extract" if mode=="extract" else "fit"}_pulse_ablation.py'),'--job',str(job),'--check-only']
            checks.append(json.loads(subprocess.check_output(command,text=True)))
    save(OUT/(mode+'_package_QA.json'),dict(actual_payload=True,zero_energy_fits=True,records=checks,**resources(start)))
    spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage80');(spool/'logs').mkdir(parents=True,exist_ok=True)
    worker=spool/'worker_v1.sh';source=REPO/'AnalysisZipFramework/submission/run_ml_pulse_ablation.sh'
    if worker.exists():assert worker.read_bytes()==source.read_bytes()
    else:worker.write_bytes(source.read_bytes())
    submit=REPO/f'AnalysisZipFramework/submission/ml_pulse_ablation_{mode}.sub'
    dry=subprocess.check_output(['condor_submit','-dry-run',str(spool/(mode+'_dryrun.ads')),str(submit)],text=True)
    ads=(spool/(mode+'_dryrun.ads')).read_text();compact=''.join(ads.split())
    assert 'MaxRuntime=1800' in compact and 'RequestMemory=3000' in compact and 'RequestCpus=1' in compact
    save(OUT/(mode+'_dryrun.json'),dict(output=dry,MaxRuntime=1800,RequestCpus=1,RequestMemory_MB=3000))
    submitted=subprocess.check_output(['condor_submit','-terse',str(submit)],text=True);cluster=int(submitted.split('.')[0])
    attrs='ClusterId,ProcId,JobStatus,RequestCpus,RequestMemory,MaxRuntime,Args'
    scheduled=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes',attrs],text=True))
    assert len(scheduled)==4 and all(r['RequestCpus']==1 and r['RequestMemory']==3000 and r['MaxRuntime']==1800 for r in scheduled)
    save(OUT/(mode+'_submission.json'),dict(mode=mode,cluster=cluster,submitted_jobs=4,payload_bytes=payload.stat().st_size,
        paths=paths,ads=scheduled,submitted_utc=stamp(),**resources(start)))
    print(submitted,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['extract','fit']);a=p.parse_args();main(a.mode)
