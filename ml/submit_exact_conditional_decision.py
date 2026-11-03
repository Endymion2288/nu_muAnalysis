#!/usr/bin/env python3
"""Stage76 actual-package startup QA and four fixed inference jobs."""
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from exact_conditional_decision import *


def main():
    start=begin();assert json.loads((OUT/'pilot.json').read_text())['passed']
    assert not (OUT/'cluster.txt').exists(), 'no repeated formal submission'
    payload=REPO/'software/energy-ml-exact-decision-stage76.tar.gz';assert not payload.exists()
    paths=['ml/exact_conditional_decision.py','ml/conditional_decision.py','ml/run_exact_conditional_decision.py',
        'ml/conditional_hypotheses.py','ml/energy_reweight.py','ml/group_risk.py','ml/expert_combination.py',
        'ml/audited_features.py','ml/support_augmentation.py','workbook/stage76_energy_ml/protocol.json',
        'workbook/stage76_energy_ml/proposals.json','ntuples/energy_ml_stage76/input.npz']
    paths += [f'ml/artifacts/stage74/{job}/{arm}.ubj' for job in JOBS for arm in ARMS]
    with tarfile.open(payload,'w:gz',compresslevel=1) as tar:
        for name in paths:tar.add(REPO/name,arcname=name)
    checks=[]
    with tempfile.TemporaryDirectory(prefix='nu_mu_stage76_package_') as temp:
        with tarfile.open(payload) as tar:tar.extractall(temp,filter='data')
        for job in JOBS:
            (Path(temp)/'workbook/stage76_energy_ml'/job).mkdir()
            value=subprocess.check_output([sys.executable,str(Path(temp)/'ml/run_exact_conditional_decision.py'),'--job',job,'--check-only'],text=True)
            checks.append(json.loads(value))
            assert not (Path(temp)/'ml/artifacts/stage76'/job).exists()
    save(OUT/'package_startup_QA.json',dict(actual_package=True,formal_fits=0,formal_point_jobs=0,worker_precreated_directory=True,
        both_query_arms_checked=True,records=checks,**resources(start)))
    spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage76');(spool/'logs').mkdir(parents=True,exist_ok=True)
    worker=spool/'worker_v1.sh';assert not worker.exists()
    worker.write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_exact_conditional_decision.sh').read_bytes())
    submit=REPO/'AnalysisZipFramework/submission/ml_exact_conditional_decision.sub'
    dry=subprocess.check_output(['condor_submit','-dry-run',str(spool/'dryrun.ads'),str(submit)],text=True)
    ads=(spool/'dryrun.ads').read_text();compact=''.join(ads.split())
    assert 'MaxRuntime=1800' in compact and 'RequestMemory=3000' in compact and 'RequestCpus=1' in compact
    (OUT/'condor_dryrun.txt').write_text(dry+'\n'+ads)
    result=subprocess.check_output(['condor_submit','-terse',str(submit)],text=True)
    (OUT/'cluster.txt').write_text(result);cluster=int(result.split('.')[0])
    ads=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes',
        'ClusterId,ProcId,JobStatus,RequestCpus,RequestMemory,MaxRuntime,Args'],text=True))
    assert len(ads)==4 and all((a['RequestCpus'],a['RequestMemory'],a['MaxRuntime'])==(1,3000,1800) for a in ads)
    save(OUT/'scheduled_ads.json',ads)
    save(OUT/'package.json',dict(paths=paths,payload_bytes=payload.stat().st_size,cluster=cluster,submitted_jobs=4,
        actual_package_startup_passed=True,**resources(start)))
    print(result);print(json.dumps(ads,indent=2))


if __name__=='__main__':main()
