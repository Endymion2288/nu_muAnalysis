"""Small matched original-chain replay with read-only birth/crossing observer."""
import concurrent.futures,gzip,json,os,shutil,subprocess,sys,time
from pathlib import Path
from stage131_pilot import DATASETS
ROOT=Path.cwd();OUT=ROOT/'workbook/stage176_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage176'
def worker(index,preflight=False):
    with gzip.open(ROOT/'ntuples/energy_ml_stage131/production_cases.json.gz','rt') as f:case=next(r for r in json.load(f) if r['frame_index']==index)
    with gzip.open(ROOT/'ntuples/energy_ml_stage131/parent_evidence.json.gz','rt') as f:old=next(r['reports'] for r in json.load(f) if r['index']==index)
    assert case['role']==1;work=ROOT/f'chain_{index}';work.mkdir();env=os.environ.copy();env['NU_MU_STAGE176_SEED']=str(case['seed'])
    for k,v in DATASETS.items():env[k]='/cvmfs/geant4.cern.ch/share/data/'+v
    tick=time.perf_counter();report=dict(index=index,case=case,steps=[],successful=False)
    def run(name,cmd):
        start=time.perf_counter();log=OUT/f'parent_{index}_{name}.log'
        with log.open('w') as stream:r=subprocess.run(['/usr/bin/time','-v','-o',str(OUT/f'parent_{index}_{name}_time.txt'),*cmd],cwd=work,env=env,stdout=stream,stderr=subprocess.STDOUT)
        report['steps'].append(dict(name=name,command=cmd,returncode=r.returncode,wall_s=time.perf_counter()-start))
        (OUT/f'parent_{index}_report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(index,name,r.returncode,flush=True)
        if r.returncode:print(log.read_text()[-7000:],flush=True);raise RuntimeError((index,name,r.returncode))
    base=f'FaserMC-Stage131Nu-990131-{index:05d}-stage131';hits=base+'-HITS.root';rdo=base+'-RDO.root';rec=base+'-xAOD.root'
    sim=[sys.executable,str(ROOT/'ml/stage176_simulate.py'),case['EVNT'],hits,'--geom','TI12MC04','--G4_phys','FTFP_BERT','--skip',str(case['entry']),'-n','1']
    run('sim',sim);lineage=json.loads((work/'lineage.jsonl').read_text().strip())
    for key,v in old['summary']['lineage'].items():assert lineage[key]==v,(key,'legacy fields differ')
    with gzip.open(CACHE/f'parent_{index}_lineage.json.gz','wt') as f:json.dump(lineage,f,separators=(',',':'))
    snapshot=CACHE/f'parent_{index}_qa_hits.json.gz'
    run('hitscheck',[sys.executable,str(ROOT/'ml/stage131_hitscheck.py'),str(work/hits),str(work/'lineage.jsonl'),str(OUT/f'parent_{index}_hitscheck.json'),'before',str(snapshot)])
    with gzip.open(snapshot,'rt') as f:saved=json.load(f)
    for name in ['VetoNuHits','VetoHits','TriggerHits','PreshowerHits','EcalHits']:
        rows=lineage['daq_hits'].get(name,[]);assert len(rows)==len(saved[name])==len(lineage['daq_birth_groups'].get(name,[]))
        for live,persist in zip(rows,saved[name]):
            assert len(live)==14 and live[4]==persist[0] and live[7]==persist[3]
            assert abs(live[5]-persist[1])<=1.1e-5+abs(live[5])*2e-7
    if preflight:
        with gzip.open(ROOT/'ntuples/energy_ml_stage135/parent_50_qa_hits.json.gz','rt') as f:assert saved==json.load(f)
        env['NU_MU_STAGE176_OBSERVER']='0';(work/hits).unlink();(work/'PoolFileCatalog.xml').unlink(missing_ok=True)
        run('sim_unobserved',sim)
        run('noninterference',[sys.executable,str(ROOT/'ml/stage131_hitscheck.py'),str(work/hits),str(work/'lineage.jsonl'),str(OUT/f'parent_{index}_noninterference.json'),'after',str(snapshot)])
    seed=case['seed']+1 if index==50 else 650000000+10000*index
    run('digi',[sys.executable,str(ROOT/'ml/stage129_digitize.py'),hits,str(seed),str(OUT/f'parent_{index}_rng.json')])
    rng=json.loads((OUT/f'parent_{index}_rng.json').read_text());(OUT/f'parent_{index}_rng.json').write_text(json.dumps({k:dict(seed=v['seed'],before_length=len(v['state']),after_length=len(v['after']),advanced=v['state']!=v['after']) for k,v in rng.items()},indent=2)+'\n')
    run('reco',['faser_reco.py','--isMC','--geom','TI12MC04','--nevents','1',rdo])
    run('ntuple',[sys.executable,str(ROOT/'ml/stage176_ntuple.py'),'--isMC','--geom','TI12MC04','--CKFTrackType','merge','--nevents','1','--outfile','ntuple.root',rec])
    run('S0',['env','-i','PATH=/usr/bin:/bin','HOME='+os.environ['HOME'],'USER='+os.environ.get('USER','xcheng'),'PYTHONNOUSERSITE=1','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','bash','-c','source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh\npython "$1/ml/stage176_extract.py" "$1" "$2" "$3"','bash',str(ROOT),str(work),str(index)])
    report.update(successful=True,legacy_fields_exact=True,hit_partition_order_exact=True,wall_s=time.perf_counter()-tick,
        scratch_ROOT_logical_B=sum(p.stat().st_size for p in work.glob('*.root')),new_independent_nu=0,energy_fits=0)
    (OUT/f'parent_{index}_report.json').write_text(json.dumps(report,indent=2)+'\n');shutil.rmtree(work);return report
if __name__=='__main__':
    phase=sys.argv[1];p=json.loads((OUT/'protocol.json').read_text())
    if phase.startswith('preflight'):results=[worker(p['preflight_index'],phase=='preflight')]
    else:
        assert phase=='pilot' and json.loads((OUT/'admission.json').read_text())['admitted']
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(worker,p['remaining_indices']))
    (OUT/f'{phase}_summary.json').write_text(json.dumps(dict(passed=True,parents=[dict(index=r['index'],successful=r['successful'],wall_s=r['wall_s']) for r in results],energy_fits=0,overall_complete=False),indent=2)+'\n')
