"""One frozen matched-support work package, only after all parent responses return."""
import json
import subprocess
import sys
import tarfile
from pathlib import Path
from stage131_common import ROOT,OUT,CACHE,protocol
assert not (OUT/'analysis_lock.json').exists()
# Transported batch archives expand only on the worker's local scratch.
for index in range(len(protocol()['batches'])):
    with tarfile.open(CACHE/f'production_{index}_result.tar.gz') as archive:
        for member in archive:
            assert member.isfile() and not member.name.startswith('/') and '..' not in Path(member.name).parts
            assert member.name.startswith(('workbook/stage131_energy_ml/','ntuples/energy_ml_stage131/'))
            payload=archive.extractfile(member).read();target=ROOT/member.name
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
            assert target.read_bytes()==payload
sequence=['prepare','fit','evaluate','mechanism','validate','plot','compact','audit']
(OUT/'analysis_lock.json').write_text(json.dumps(dict(sequence=sequence,energy_fits=18,grid=False,reserve_forward=0),indent=2)+'\n')
for phase in sequence:
    with (OUT/f'analysis_{phase}.log').open('w') as stream:
        r=subprocess.run(['/usr/bin/time','-v','-o',str(OUT/f'analysis_{phase}_time.txt'),sys.executable,str(ROOT/f'ml/stage131_{phase}.py')],stdout=stream,stderr=subprocess.STDOUT)
    print('ANALYSIS_STEP',phase,r.returncode,flush=True)
    if r.returncode:
        print((OUT/f'analysis_{phase}.log').read_text()[-6000:],flush=True)
        raise SystemExit(r.returncode)
(OUT/'analysis_complete.json').write_text(json.dumps(dict(sequence=sequence,successful=True,energy_fits=18,reserve_forward=0),indent=2)+'\n')
