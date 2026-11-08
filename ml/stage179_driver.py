"""Bounded single-thread parent processes, no new physics transport."""
import concurrent.futures
import json
import subprocess
import sys
import time
from pathlib import Path
OUT = Path('workbook/stage179_energy_ml')

def worker(index):
    start = time.perf_counter()
    with (OUT/f'parent_{index}_native.log').open('w') as stream:
        result = subprocess.run(['/usr/bin/time','-v','-o',str(OUT/f'parent_{index}_time.txt'),
            sys.executable,'-u','ml/stage179_native.py',str(index)],stdout=stream,stderr=subprocess.STDOUT)
    record = dict(index=index,returncode=result.returncode,wall_s=time.perf_counter()-start)
    (OUT/f'parent_{index}_execution.json').write_text(json.dumps(record,indent=2)+'\n')
    print(record,flush=True)
    if result.returncode:
        print((OUT/f'parent_{index}_native.log').read_text()[-7000:],flush=True)
        raise RuntimeError(record)
    return record

if __name__=='__main__':
    phase=sys.argv[1];p=json.loads((OUT/'protocol.json').read_text())
    if phase.startswith('preflight'):
        rows=[worker(p['preflight_index'])]
    else:
        assert phase=='full' and json.loads((OUT/'admission.json').read_text())['admitted']
        with concurrent.futures.ThreadPoolExecutor(max_workers=p['worker_processes']) as pool:
            rows=list(pool.map(worker,p['remaining_indices']))
    (OUT/f'{phase}_summary.json').write_text(json.dumps(dict(passed=True,parents=rows),indent=2)+'\n')
