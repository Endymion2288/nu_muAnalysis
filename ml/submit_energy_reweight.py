#!/usr/bin/env python3
"""Package the frozen cache once, dry-run, submit four fixed jobs and retain ads."""
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from energy_reweight import *


def main():
    assert json.loads((OUT/'pilot.json').read_text())['passed']
    assert not json.loads((OUT/'A_validation.json').read_text())['current_X_reproducible_error_found']
    assert not (OUT/'cluster.txt').exists(), 'never submit the formal jobs twice'
    payload=REPO/'software/energy-ml-reweight-stage73.tar.gz'
    paths=['ml/energy_reweight.py','ml/fit_energy_reweight.py','ml/group_risk.py','ml/expert_combination.py',
        'ml/audited_features.py','ml/support_augmentation.py','workbook/stage73_energy_ml/protocol.json',
        'ntuples/energy_ml_stage73/input.npz','workbook/stage73_energy_ml/launch_amendment.json']
    if not payload.exists():
        with tarfile.open(payload,'w:gz',compresslevel=1) as tar:
            for name in paths:tar.add(REPO/name,arcname=name)
    else:
        with tarfile.open(payload) as tar:
            for name in paths:assert tar.extractfile(name).read()==(REPO/name).read_bytes()
    checks=[]
    with tempfile.TemporaryDirectory(prefix='nu_mu_stage73_package_') as temp:
        with tarfile.open(payload) as tar:tar.extractall(temp,filter='data')
        for job in ['fold0','fold1','fold2','final']:
            (Path(temp)/'workbook/stage73_energy_ml'/job).mkdir()
            text=subprocess.check_output([sys.executable,str(Path(temp)/'ml/fit_energy_reweight.py'),'--job',job,'--check-only'],text=True)
            checks.append(json.loads(text))
    save(OUT/'package_startup_QA.json',dict(actual_package=True,worker_precreated_directory=True,formal_fits=0,records=checks))
    spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage73');(spool/'logs').mkdir(parents=True,exist_ok=True)
    worker=spool/'worker_v1.sh'
    if worker.exists():assert worker.read_bytes()==(REPO/'AnalysisZipFramework/submission/run_ml_energy_reweight.sh').read_bytes()
    else:worker.write_bytes((REPO/'AnalysisZipFramework/submission/run_ml_energy_reweight.sh').read_bytes())
    submit=REPO/'AnalysisZipFramework/submission/ml_energy_reweight.sub'
    dry=subprocess.check_output(['condor_submit','-dry-run',str(spool/'dryrun.ads'),str(submit)],text=True)
    ads=(spool/'dryrun.ads').read_text();compact=''.join(ads.split())
    assert 'MaxRuntime=1800' in compact and 'RequestMemory=3000' in compact
    (OUT/'condor_dryrun.txt').write_text(dry+'\n'+ads)
    result=subprocess.check_output(['condor_submit','-terse',str(submit)],text=True)
    cluster=int(result.split('.')[0]);(OUT/'cluster.txt').write_text(result)
    ads=json.loads(subprocess.check_output(['condor_q',str(cluster),'-json','-attributes',
        'ClusterId,ProcId,JobStatus,RequestCpus,RequestMemory,MaxRuntime,Args'],text=True))
    assert len(ads)==4
    save(OUT/'scheduled_ads.json',ads)
    save(OUT/'package.json',dict(paths=paths,payload_bytes=payload.stat().st_size,cluster=cluster,
        submitted_jobs=4,MaxRuntime1800_preserved=all(a['MaxRuntime']==1800 for a in ads)))
    print(result);print(json.dumps(ads,indent=2))


if __name__=='__main__':main()
