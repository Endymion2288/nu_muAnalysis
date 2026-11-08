"""One nonblocking scheduling/transport pass; scientific work stays in Condor."""
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage158_energy_ml'
subprocess.run([sys.executable,str(ROOT/'ml/stage158_monitor.py')],check=True)
account=json.loads((OUT/'scheduler_accounting.json').read_text())
assert not account['unresolved_ids'],account['unresolved_ids']
records={r['ClusterId']:r for r in account['jobs']}
complete=[]
for path in sorted(OUT.glob('batch_*_submission.json')):
    submit=json.loads(path.read_text());phase=submit['phase'];cluster=int(submit['result'].split('.')[0])
    row=records.get(cluster,{})
    if row.get('JobStatus')!=4:continue
    assert row.get('ExitCode')==0,(phase,row)
    if not (OUT/f'{phase}_exitcode.txt').exists():
        with tempfile.NamedTemporaryFile(prefix='nu_mu_stage158_',suffix='.tar.gz') as temp:
            subprocess.run(['xrdcp','--silent','--force',
                f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage158/{phase}_result.tar.gz',temp.name],check=True)
            with tarfile.open(temp.name,'r:gz') as archive:archive.extractall(ROOT)
    assert (OUT/f'{phase}_exitcode.txt').read_text().strip()=='0'
    complete.append(phase)
slots=4-account['live_N']
for index in range(10):
    phase=f'batch_{index:02d}'
    if slots<=0:break
    if (OUT/f'{phase}_submission.json').exists():continue
    subprocess.run([sys.executable,str(ROOT/'ml/stage158_submit.py'),phase],check=True)
    subprocess.run([sys.executable,str(ROOT/'ml/stage158_monitor.py')],check=True)
    slots-=1
print(dict(completed_batches=complete,complete_N=len(complete),all_done=len(complete)==10),flush=True)
