"""Small native REC merge and HITS tests before any large production."""
import concurrent.futures
import json
import subprocess
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage119_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage119'


def run(task):
    name=task['name'];log=OUT/f'{name}.log';tick=time.perf_counter()
    if task['type']=='merge':
        command=['faser_ntuple_maker.py','--isMC','--geom','TI12MC04','--CKFTrackType','merge',
                 '--nevents','40','--outfile',str(CACHE/f'{name}.root'),task['input']]
    else:
        command=['python',str(ROOT/'ml/stage119_hits.py'),'--input',task['input'],
                 '--events','1000','--output',str(OUT/f'{name}_hits.json')]
    with log.open('w') as f:r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=1800)
    lines=log.read_text(errors='replace').splitlines()
    evidence=[v for v in lines if any(k in v for k in ['ERROR','FATAL','WAVE-Calibration','OFLCOND','CKFTrackCollection','UseIFT','TI12MC04','exception'])]
    (OUT/f'{name}_log_excerpt.txt').write_text('\n'.join(evidence+lines[-30:])+'\n')
    log.unlink()
    return dict(task=task,command=command,exitcode=r.returncode,wall_s=time.perf_counter()-tick)


def main():
    CACHE.mkdir(exist_ok=True,parents=True);p=json.loads((OUT/'native_contract.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:r=list(pool.map(run,p['tasks']))
    (OUT/'native_results.json').write_text(json.dumps(r,indent=2)+'\n')
    print(r,flush=True)


if __name__=='__main__':main()
