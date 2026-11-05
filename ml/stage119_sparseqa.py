"""Native sparse/full reconstruction equivalence on previously run 40 parents."""
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage119'


def main():
    CACHE.mkdir(parents=True,exist_ok=True)
    results=[]
    for source in json.loads((OUT/'recoqa_contract.json').read_text())['tasks']:
        run=source['run'];work=ROOT/f'sparseqa2_{run}';work.mkdir()
        (work/'input-RDO.root').symlink_to(source['input'])
        request=dict(entries=[0,3,9,15,23,39],parent_N=40,rdo='input-RDO.root')
        (work/'request.json').write_text(json.dumps(request))
        commands=[['python',str(ROOT/'ml/stage119_sparse_reco.py'),'request.json'],
            ['faser_ntuple_maker.py','--isMC','--geom','TI12MC04','--CKFTrackType','merge','--nevents','-1',
             '--outfile',str(CACHE/f'sparseqa2_{run}.root'),'input-xAOD.root']]
        for i,command in enumerate(commands):
            log=OUT/f'sparseqa2_{run}_{i}.log'
            with log.open('w') as f:r=subprocess.run(command,cwd=work,stdout=f,stderr=subprocess.STDOUT,timeout=900)
            lines=log.read_text(errors='replace').splitlines()
            errors=[v for v in lines if any(k in v for k in ['ERROR','FATAL'])]
            (OUT/f'sparseqa2_{run}_{i}_excerpt.txt').write_text('\n'.join(errors+lines[-15:])+'\n');log.unlink()
            results.append(dict(run=run,command=command,exitcode=r.returncode))
            assert r.returncode==0
    (OUT/'sparseqa2_results.json').write_text(json.dumps(results,indent=2)+'\n')


if __name__=='__main__':main()
