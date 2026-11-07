"""Run only the predeclared Ecal cache controls and retain failures."""
import concurrent.futures
import json
import subprocess
import sys
import time
from pathlib import Path

OUT = Path('workbook/stage144_energy_ml')


def worker(index):
    tick = time.perf_counter()
    with (OUT/f'parent_{index}.log').open('w') as stream:
        result = subprocess.run(['/usr/bin/time', '-v', '-o', str(OUT/f'parent_{index}_time.txt'),
                                 sys.executable, '-u', 'ml/stage144_native.py', str(index)],
                                stdout=stream, stderr=subprocess.STDOUT)
    record = dict(index=index, returncode=result.returncode, wall_s=time.perf_counter()-tick)
    (OUT/f'parent_{index}_execution.json').write_text(json.dumps(record, indent=2)+'\n')
    if result.returncode:
        print((OUT/f'parent_{index}.log').read_text()[-6000:], flush=True)
    else:
        text = (OUT/f'parent_{index}.log').read_text()
        if len(text) > 14000:
            (OUT/f'parent_{index}.log').write_text(text[:4000]+'\n[successful log compacted]\n'+text[-10000:])
    return record


def main():
    phase = sys.argv[1]
    if phase in ['preflight', 'preflight_repair', 'preflight_rngmap', 'preflight_idheader']:
        rows = [worker(50)]
    else:
        admission = json.loads((OUT/'pilot_admission.json').read_text())
        assert phase == 'pilot' and admission['admitted']
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            rows = list(pool.map(worker, admission['indices']))
    (OUT/f'{phase}_executions.json').write_text(json.dumps(rows, indent=2)+'\n')
    assert all(row['returncode'] == 0 for row in rows)


if __name__ == '__main__':
    main()
