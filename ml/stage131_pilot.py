"""Finite natural-parent full-chain pilot. No training or energy prediction."""
import concurrent.futures
import gzip
import json
import os
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path.cwd();OUT=ROOT/'workbook/stage131_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage131'
DATASETS=dict(G4LEDATA='G4EMLOW7.9.1',G4LEVELGAMMADATA='PhotonEvaporation5.5',G4RADIOACTIVEDATA='RadioactiveDecay5.4',G4PARTICLEXSDATA='G4PARTICLEXS2.1',G4NEUTRONHPDATA='G4NDL4.6',G4SAIDXSDATA='G4SAIDDATA2.0',G4ABLADATA='G4ABLA3.1',G4INCLDATA='G4INCL1.0',G4ENSDFSTATEDATA='G4ENSDFSTATE2.2',G4REALSURFACEDATA='RealSurface2.1.1')

def worker(case):
    index=case['frame_index'];work=ROOT/f'chain_{index}';work.mkdir();tick=time.perf_counter();steps=[]
    for k,v in DATASETS.items():os.environ[k]=str(Path('/cvmfs/geant4.cern.ch/share/data')/v)
    env=os.environ.copy();env['NU_MU_STAGE131_SEED']=str(case['seed'])
    summary=dict(case=case,steps=steps,successful=False)
    def run(name,cmd):
        log=OUT/f'parent_{index}_{name}.log';timing=OUT/f'parent_{index}_{name}_time.txt';start=time.perf_counter()
        with log.open('w') as stream:r=subprocess.run(['/usr/bin/time','-v','-o',str(timing)]+cmd,cwd=work,env=env,stdout=stream,stderr=subprocess.STDOUT)
        steps.append(dict(name=name,command=cmd,returncode=r.returncode,wall_s=time.perf_counter()-start))
        summary.update(wall_s=time.perf_counter()-tick);(OUT/f'parent_{index}_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print('PARENTSTEP',index,name,r.returncode,round(steps[-1]['wall_s'],2),flush=True)
        if r.returncode:
            print(log.read_text()[-6000:],flush=True)
            raise RuntimeError((index,name,r.returncode))
        if log.stat().st_size>10000:
            text=log.read_text();log.write_text(text[:2000]+'\n[successful verbose log compacted; exact command and timing retained]\n'+text[-8000:])
    name=f'FaserMC-Stage131Nu-990131-{index:05d}-stage131';hits=name+'-HITS.root';rdo=name+'-RDO.root';rec=name+'-xAOD.root'
    run('sim',[sys.executable,str(ROOT/'ml/stage131_simulate.py'),case['EVNT'],hits,'--geom','TI12MC04','--G4_phys','FTFP_BERT','--skip',str(case['entry']),'-n','1'])
    lineage=[json.loads(x) for x in (work/'lineage.jsonl').read_text().splitlines()];assert len(lineage)==1
    summary['lineage']=lineage[0]
    check=[sys.executable,str(ROOT/'ml/stage131_hitscheck.py'),str(work/hits),str(work/'lineage.jsonl'),str(OUT/f'parent_{index}_hitscheck.json')]
    if index==50:check+=['before',str(CACHE/'observer_noninterference_hits.json.gz')]
    run('hitscheck',check)
    if index==50:
        env['NU_MU_STAGE131_OBSERVER']='0'
        (work/hits).unlink()
        (work/'PoolFileCatalog.xml').unlink(missing_ok=True)
        run('sim_unobserved',[sys.executable,str(ROOT/'ml/stage131_simulate.py'),case['EVNT'],hits,'--geom','TI12MC04','--G4_phys','FTFP_BERT','--skip',str(case['entry']),'-n','1'])
        run('noninterference',[sys.executable,str(ROOT/'ml/stage131_hitscheck.py'),str(work/hits),str(work/'lineage.jsonl'),str(OUT/'observer_noninterference.json'),'after',str(CACHE/'observer_noninterference_hits.json.gz')])
        env['NU_MU_STAGE131_OBSERVER']='1'
    # The first already-running preflight keeps its recorded original seed.
    # Other parents get nonoverlapping five-detector private seed ranges.
    wave_seed=case['seed']+1 if index==50 else 650000000+10000*index
    summary['digitizer_seed_base']=wave_seed
    run('digi',[sys.executable,str(ROOT/'ml/stage129_digitize.py'),hits,str(wave_seed),str(OUT/f'parent_{index}_rng.json')])
    rng_path=OUT/f'parent_{index}_rng.json';rng=json.loads(rng_path.read_text())
    if index==50:
        with gzip.open(CACHE/'pilot_private_rng_states.json.gz','wt') as f:json.dump(rng,f,separators=(',',':'))
    rng_path.write_text(json.dumps({k:dict(seed=v['seed'],state_characters=len(v['state']),after_characters=len(v['after']),advanced=v['state']!=v['after']) for k,v in rng.items()},indent=2)+'\n')
    run('reco',['faser_reco.py','--isMC','--geom','TI12MC04','--nevents','1',rdo])
    run('ntuple',['faser_ntuple_maker.py','--isMC','--geom','TI12MC04','--CKFTrackType','merge','--nevents','1','--outfile','ntuple.root',rec])
    (work/'case.json').write_text(json.dumps(case))
    run('extract',['env','-i','PATH=/usr/bin:/bin','HOME='+os.environ['HOME'],'USER='+os.environ.get('USER','xcheng'),'PYTHONNOUSERSITE=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','bash','-c','source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh\npython "$1/ml/stage131_extract.py" "$1" "$2"','bash',str(ROOT),str(work)])
    summary.update(successful=True,wall_s=time.perf_counter()-tick)
    summary['scratch_ROOT_logical_B']=sum(p.stat().st_size for p in work.glob('*.root'))
    summary['intermediate_ROOT_retained']=False
    (OUT/f'parent_{index}_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    # ROOT exists only on worker scratch and is never transported to EOS.
    shutil.rmtree(work)
    return dict(index=index,successful=True,wall_s=summary['wall_s'])

def main():
    with gzip.open(CACHE/'frame.json.gz','rt') as f:frame=json.load(f)
    p=json.loads((OUT/'pilot_contract.json').read_text());indices=p['pilot_indices'];results=[]
    preflight=OUT/'preflight_results.json'
    if preflight.exists():
        checked=json.loads(preflight.read_text());assert checked['successful'] and checked['index']==50
        results.append(dict(checked,reused_preflight=True));indices=[i for i in indices if i!=50]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(worker,frame[i]):i for i in indices}
        for future in concurrent.futures.as_completed(futures):
            i=futures[future]
            try:results.append(future.result())
            except Exception as e:results.append(dict(index=i,successful=False,error=repr(e)))
    (OUT/'pilot_results.json').write_text(json.dumps(results,indent=2)+'\n')
    assert all(r['successful'] for r in results),results

if __name__=='__main__':main()
