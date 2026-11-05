"""Bounded proof that existing hadronization HITS can deliver actual readouts."""
import concurrent.futures
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage119'


def run(task):
    run=task['run'];work=ROOT/f'pythiaqa_{run}';work.mkdir();(work/'input-HITS.root').symlink_to(task['input'])
    commands=[['faser_digi.py','--geom','TI12MC04','--nevts','40','input-HITS.root'],
        ['faser_reco.py','--isMC','--geom','TI12MC04','--nevents','-1','input-RDO.root'],
        ['faser_ntuple_maker.py','--isMC','--geom','TI12MC04','--CKFTrackType','merge','--nevents','-1','--outfile',str(CACHE/f'pythiaqa_{run}.root'),'input-xAOD.root']]
    results=[]
    for i,command in enumerate(commands):
        log=OUT/f'pythiaqa_{run}_{i}.log'
        with log.open('w') as f:
            r=subprocess.run(['/usr/bin/time','-v','-o',str(OUT/f'pythiaqa_{run}_{i}_time.txt')]+command,cwd=work,stdout=f,stderr=subprocess.STDOUT,timeout=900)
        lines=log.read_text(errors='replace').splitlines();errors=[v for v in lines if any(k in v for k in ['ERROR','FATAL','DigitizerSamples','DigitizerPeriod','improved digitization','WAVE-Calibration','OFLCOND'])]
        (OUT/f'pythiaqa_{run}_{i}_excerpt.txt').write_text('\n'.join(errors+lines[-15:])+'\n');log.unlink()
        results.append(dict(run=run,step=i,command=command,exitcode=r.returncode))
        if r.returncode:break
    return results


def main():
    CACHE.mkdir(parents=True,exist_ok=True)
    p=json.loads((OUT/'pythiaqa_contract.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:r=list(pool.map(run,p['tasks']))
    (OUT/'pythiaqa_results.json').write_text(json.dumps(r,indent=2)+'\n')


if __name__=='__main__':main()
