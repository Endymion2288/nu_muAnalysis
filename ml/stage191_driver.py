"""Eight independent source readers concurrently, each reusing its Athena runtime."""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT=Path.cwd();OUT=ROOT/'workbook/stage191_energy_ml';phase=sys.argv[1]
family=int(phase.split('_')[1])
groups=(json.loads((OUT/f'{phase}_plan.json').read_text())['groups'] if phase.startswith('repair') else list(range(family*7,min(family*7+7,35))))


def run(group):
    # POOL and geometry libraries may create process-local bookkeeping files.
    # Keep these independent while sharing read-only libraries and final output dirs.
    work=ROOT/f'reader_{group}'
    work.mkdir()
    for name in ['ml','workbook','ntuples','stage188_bridge.so']:
        (work/name).symlink_to(ROOT/name)
    with (OUT/f'full_{group}.log').open('w') as log:
        result=subprocess.run(['/usr/bin/time','-v','-o',str(OUT/f'full_{group}_time.txt'),sys.executable,'-u','ml/stage191_native.py','full',str(group)],cwd=work,stdout=log,stderr=subprocess.STDOUT)
    return dict(group=group,exit=result.returncode)


if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=7) as pool:rows=list(pool.map(run,groups))
    (OUT/f'{phase}_driver.json').write_text(json.dumps(rows,indent=2)+'\n')
    assert all(r['exit']==0 for r in rows)
