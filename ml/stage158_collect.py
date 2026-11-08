"""Transport one terminal stage158 result without scientific computation."""
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage158_energy_ml'
phase=sys.argv[1]
subprocess.run([sys.executable,str(ROOT/'ml/stage158_monitor.py')],check=True)
account=json.loads((OUT/'scheduler_accounting.json').read_text())
cluster=int(json.loads((OUT/f'{phase}_submission.json').read_text())['result'].split('.')[0])
row=next((r for r in account['jobs'] if r['ClusterId']==cluster),None)
assert row is not None and row['JobStatus'] in [3,4],row
with tempfile.NamedTemporaryFile(prefix='nu_mu_stage158_',suffix='.tar.gz') as temp:
    subprocess.run(['xrdcp','--silent','--force',
        f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage158/{phase}_result.tar.gz',temp.name],check=True)
    with tarfile.open(temp.name,'r:gz') as archive:archive.extractall(ROOT)
print('COLLECTED',phase,'exit',row.get('ExitCode'),flush=True)
raise SystemExit(row.get('ExitCode',1))
