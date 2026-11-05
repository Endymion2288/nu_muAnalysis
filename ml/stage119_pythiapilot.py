"""Parallel native generator-parent pilot for a fixed hadronization comparison."""
import concurrent.futures
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml'


def run(index):
    log=OUT/f'pythia_parent_{index}.log'
    with log.open('w') as f:r=subprocess.run(['python',str(ROOT/'ml/stage119_pythiaparents.py'),'--index',str(index)],stdout=f,stderr=subprocess.STDOUT,timeout=900)
    lines=log.read_text(errors='replace').splitlines();errors=[v for v in lines if any(k in v for k in ['ERROR','FATAL'])]
    (OUT/f'pythia_parent_{index}_excerpt.txt').write_text('\n'.join(errors+lines[-8:])+'\n');log.unlink()
    return dict(index=index,exitcode=r.returncode)


def main():
    p=json.loads((OUT/'pythia_contract.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:r=list(pool.map(run,range(len(p['sources']))))
    (OUT/'pythiapilot.json').write_text(json.dumps(r,indent=2)+'\n');assert all(q['exitcode']==0 for q in r)


if __name__=='__main__':main()
