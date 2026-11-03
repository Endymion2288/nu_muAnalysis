"""Collect the two successful fixed stage82 training jobs without duplicating input."""
import json
import subprocess
import tarfile
from audited_features import REPO
from support_augmentation import save
from k_support_curve import job_history
from pathlib import Path

OUT=REPO/'workbook/stage82_energy_ml'
CACHE=REPO/'ntuples/energy_ml_stage82'

if __name__=='__main__':
    sub=json.loads((OUT/'curve_submission.json').read_text())
    log=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage82_curve/logs')/f'curve.{sub["cluster"]}.log'
    history=job_history(log,sub)
    assert len(history)==2 and all(r['JobStatus']==4 and r['ExitCode']==0 and r['NumJobStarts']==1 and 900<=r['MaxRuntime']<=1800 and r['RequestCpus']==1 and r['RequestMemory']==3000 for r in history)
    (OUT/'curve_events.log').write_bytes(log.read_bytes())
    assert sum(r['RemoteUserCpu']+r['RemoteSysCpu'] for r in history)<=1800
    for arm in ['half','full']:
        with tarfile.open(CACHE/f'curve_{arm}.tar.gz') as t:
            for m in t.getmembers():
                if m.isdir():continue
                assert m.isfile() and '..' not in m.name and m.name.startswith(('workbook/stage82_energy_ml/',f'ml/artifacts/stage82/{arm}/'))
                dest=REPO/m.name
                value=t.extractfile(m).read()
                if dest.exists():assert dest.read_bytes()==value
                else:
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    dest.write_bytes(value)
    save(OUT/'curve_history.json',history)
    print('collected two one-start jobs, six fixed fits')
