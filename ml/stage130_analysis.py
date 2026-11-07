"""One immutable, sequential full-source preparation/fit/evaluation work package."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'


def main():
    assert not (OUT / 'analysis_lock.json').exists(), 'Do not repeat the frozen work package'
    lock = dict(sequence=['prepare', 'supportcurve', 'fit', 'evaluate', 'validate',
                          'fluxdiagnostics', 'plot', 'compactverify'],
        formal_fits=9, architecture_search=False, reserve_forward=0,
        membership_frozen_before_fit=True, source_denominator=666)
    (OUT / 'analysis_lock.json').write_text(json.dumps(lock, indent=2)+'\n')
    for phase in lock['sequence']:
        with (OUT / f'analysis_{phase}.log').open('w') as log:
            subprocess.run(['/usr/bin/time', '-v', '-o', str(OUT / f'analysis_{phase}_time.txt'),
                            sys.executable, str(ROOT / f'ml/stage130_{phase}.py')],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        print('Completed', phase, flush=True)
    (OUT / 'analysis_complete.json').write_text(json.dumps(lock, indent=2)+'\n')


if __name__ == '__main__':
    main()
