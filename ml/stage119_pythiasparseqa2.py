"""Sparse digitization QA against the already measured full forty parents."""
import concurrent.futures
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage119'


def run(task):
    run=task['run'];work=ROOT/f'pythiasparseqa2_{run}';work.mkdir()
    (work/'input-HITS.root').symlink_to(task['input'])
    (work/'request.json').write_text(json.dumps(dict(entries=[0,3,9,15,23,39],parent_N=40,hits='input-HITS.root')))
    commands=[['python',str(ROOT/'ml/stage119_sparse_digi.py'),'request.json'],
        ['faser_reco.py','--isMC','--geom','TI12MC04','--nevents','-1','input-RDO.root'],
        ['faser_ntuple_maker.py','--isMC','--geom','TI12MC04','--CKFTrackType','merge','--nevents','-1','--outfile',str(CACHE/f'pythiasparseqa2_{run}.root'),'input-xAOD.root']]
    results=[]
    for i,command in enumerate(commands):
        log=OUT/f'pythiasparseqa2_{run}_{i}.log'
        with log.open('w') as f:
            r=subprocess.run(['/usr/bin/time','-v','-o',str(OUT/f'pythiasparseqa2_{run}_{i}_time.txt')]+command,cwd=work,stdout=f,stderr=subprocess.STDOUT,timeout=900)
        lines=log.read_text(errors='replace').splitlines()
        (OUT/f'pythiasparseqa2_{run}_{i}_excerpt.txt').write_text('\n'.join([v for v in lines if any(k in v for k in ['ERROR','FATAL'])]+lines[-15:])+'\n');log.unlink()
        results.append(dict(run=run,step=i,command=command,exitcode=r.returncode))
        assert r.returncode==0
    return results


def main():
    CACHE.mkdir(parents=True,exist_ok=True)
    tasks=json.loads((OUT/'pythiaqa_contract.json').read_text())['tasks']
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:r=list(pool.map(run,tasks))
    (OUT/'pythiasparseqa2.json').write_text(json.dumps(r,indent=2)+'\n')


if __name__=='__main__':main()
