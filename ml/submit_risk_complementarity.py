#!/usr/bin/env python3
"""Actual-package startup QA, then exactly four frozen source pipeline jobs."""
import subprocess,sys,tarfile,tempfile
from pathlib import Path
from risk_complementarity import *


def main():
    start=begin();assert json.loads((OUT/'pilot.json').read_text())['passed']
    assert json.loads((OUT/'input_validation.json').read_text())['passed']
    assert not (OUT/'cluster.txt').exists()
    payload=REPO/'software/energy-ml-risk-complementarity-stage78.tar.gz'
    paths=['ml/risk_complementarity.py','ml/fit_risk_complementarity.py','ml/support_augmentation.py','ml/energy_reweight.py',
        'ml/group_risk.py','ml/expert_combination.py','ml/audited_features.py',
        'workbook/stage78_energy_ml/protocol.json','ntuples/energy_ml_stage78/input.npz']
    assert not payload.exists()
    with tarfile.open(payload,'w:gz',compresslevel=1) as tar:
        for name in paths:tar.add(REPO/name,arcname=name)
    checks=[]
    with tempfile.TemporaryDirectory(prefix='nu_mu_stage78_package_') as temp:
        with tarfile.open(payload) as tar:tar.extractall(temp,filter='data')
        for job in JOBS:
            (Path(temp)/'workbook/stage78_energy_ml'/job).mkdir()
            value=subprocess.check_output([sys.executable,str(Path(temp)/'ml/fit_risk_complementarity.py'),'--job',job,'--check-only'],text=True,timeout=60)
            checks.append(json.loads(value))
    save(OUT/'package_startup_QA.json',dict(passed=True,actual_package=True,worker_precreated_report_directory=True,records=checks,**resources(start)))
    spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage78');(spool/'logs').mkdir(parents=True,exist_ok=True)
    worker=spool/'worker_v1.sh';assert not worker.exists();worker.write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_risk_complementarity.sh').read_bytes())
    sub=REPO/'AnalysisZipFramework/submission/ml_risk_complementarity.sub'
    dry=subprocess.check_output(['condor_submit','-dry-run',str(spool/'dryrun.ads'),str(sub)],text=True,timeout=60)
    ads=(spool/'dryrun.ads').read_text();compact=''.join(ads.split())
    assert 'MaxRuntime=3600' in compact and 'RequestMemory=3000' in compact and 'RequestCpus=1' in compact
    (OUT/'condor_dryrun.txt').write_text(dry+'\n'+ads)
    result=subprocess.check_output(['condor_submit','-terse',str(sub)],text=True,timeout=60)
    cluster=int(result.split('.')[0]);(OUT/'cluster.txt').write_text(result)
    ads=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes',
        'ClusterId,ProcId,JobStatus,RequestCpus,RequestMemory,MaxRuntime,Args'],text=True,timeout=60))
    save(OUT/'scheduled_ads.json',ads)
    save(OUT/'package.json',dict(paths=paths,payload_bytes=payload.stat().st_size,cluster=cluster,submitted_jobs=4,
        scheduled_resource_contract_preserved=len(ads)==4 and all(a['MaxRuntime']==3600 and a['RequestCpus']==1 and a['RequestMemory']==3000 for a in ads),**resources(start)))
    print(result);print(json.dumps(ads,indent=2))


if __name__=='__main__':main()
