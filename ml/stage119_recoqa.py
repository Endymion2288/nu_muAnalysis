"""Recover compatible observables by the proven RDO reconstruction path."""
import concurrent.futures
import json
import subprocess
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage119'


def run(task):
    run=task['run'];work=ROOT/f'recoqa_{run}';work.mkdir();(work/'input-RDO.root').symlink_to(task['input'])
    tick=time.perf_counter();commands=[]
    commands.append(['faser_reco.py','--isMC','--geom','TI12MC04','--nevents','40','input-RDO.root'])
    commands.append(['faser_ntuple_maker.py','--isMC','--geom','TI12MC04','--CKFTrackType','merge','--nevents','-1',
                     '--outfile',str(CACHE/f'recoqa_{run}.root'),'input-xAOD.root'])
    result=dict(task=task,steps=[])
    for i,command in enumerate(commands):
        log=OUT/f'recoqa_{run}_{i}.log';timefile=OUT/f'recoqa_{run}_{i}_time.txt'
        with log.open('w') as f:
            p=subprocess.run(['/usr/bin/time','-v','-o',str(timefile)]+command,cwd=work,stdout=f,stderr=subprocess.STDOUT,timeout=900)
        lines=log.read_text(errors='replace').splitlines()
        evidence=[l for l in lines if any(k in l for k in ['ERROR','FATAL','WAVE-Calibration','OFLCOND','CKFTrackCollection','UseIFT'])]
        (OUT/f'recoqa_{run}_{i}_excerpt.txt').write_text('\n'.join(evidence+lines[-20:])+'\n');log.unlink()
        result['steps'].append(dict(command=command,exitcode=p.returncode))
        if p.returncode:break
    result['wall_s']=time.perf_counter()-tick
    # xAOD intermediates are never transported.
    return result


def main():
    CACHE.mkdir(parents=True,exist_ok=True);p=json.loads((OUT/'recoqa_contract.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:r=list(pool.map(run,p['tasks']))
    (OUT/'recoqa_results.json').write_text(json.dumps(r,indent=2)+'\n');print(r,flush=True)


if __name__=='__main__':main()
