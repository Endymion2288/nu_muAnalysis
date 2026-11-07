"""One actual-hit ancestry instrumentation preflight; no model or new nu."""
import gzip
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from stage131_pilot import DATASETS

STAGE=int(os.environ.get('NU_MU_RESPONSE_STAGE','142'))
ROOT=Path.cwd();OUT=ROOT/f'workbook/stage{STAGE}_energy_ml';CACHE=ROOT/f'ntuples/energy_ml_stage{STAGE}'

def worker(index):
    with gzip.open(ROOT/'ntuples/energy_ml_stage131/production_cases.json.gz','rt') as f:
        case=next(r for r in json.load(f) if r['frame_index']==index)
    with gzip.open(ROOT/'ntuples/energy_ml_stage131/parent_evidence.json.gz','rt') as f:
        old=next(r['reports'] for r in json.load(f) if r['index']==index)
    assert case['role']==1
    work=ROOT/f'chain_{index}';work.mkdir();env=os.environ.copy()
    env['NU_MU_STAGE142_SEED']=str(case['seed'])
    for key,value in DATASETS.items():env[key]='/cvmfs/geant4.cern.ch/share/data/'+value
    report=dict(case=case,steps=[],successful=False);tick=time.perf_counter()
    def run(name,cmd,taskcwd=None):
        start=time.perf_counter();log=OUT/f'parent_{index}_{name}.log'
        with log.open('w') as f:
            result=subprocess.run(['/usr/bin/time','-v','-o',str(OUT/f'parent_{index}_{name}_time.txt'),*cmd],cwd=work if taskcwd is None else taskcwd,env=env,stdout=f,stderr=subprocess.STDOUT)
        report['steps'].append(dict(name=name,command=cmd,returncode=result.returncode,wall_s=time.perf_counter()-start))
        (OUT/('preflight_report.json' if index==50 else f'parent_{index}_report.json')).write_text(json.dumps(report,indent=2)+'\n')
        if result.returncode:print(log.read_text()[-5000:],flush=True)
        assert result.returncode==0,(name,result.returncode)
        if log.stat().st_size>14000:
            text=log.read_text();log.write_text(text[:4000]+'\n[successful log compacted]\n'+text[-10000:])
    hits=f'FaserMC-Stage131Nu-990131-{index:05d}-stage131-HITS.root'
    run('sim',[sys.executable,str(ROOT/'ml/stage142_simulate.py'),case['EVNT'],hits,'--geom','TI12MC04','--G4_phys','FTFP_BERT','--skip',str(case['entry']),'-n','1'])
    observed=json.loads((work/'lineage.jsonl').read_text().strip())
    for key,value in old['summary']['lineage'].items():assert observed[key]==value,(key,'legacy differs')
    report['legacy_fields_exact']=True
    (OUT/f'parent_{index}_lineage.json').write_text(json.dumps(observed,indent=2)+'\n')
    snapshot=CACHE/f'parent_{index}_qa_hits.json.gz'
    run('hitscheck',[sys.executable,str(ROOT/'ml/stage131_hitscheck.py'),str(work/hits),str(work/'lineage.jsonl'),str(OUT/f'parent_{index}_hitscheck.json'),'before',str(snapshot)])
    with gzip.open(snapshot,'rt') as f:persistent=json.load(f)
    if index==50:
        with gzip.open(ROOT/'ntuples/energy_ml_stage135/parent_50_qa_hits.json.gz','rt') as f:reference=json.load(f)
        assert persistent==reference
    validation=[]
    for name in ['VetoNuHits','VetoHits','TriggerHits','PreshowerHits','EcalHits']:
        live=observed['daq_hits'].get(name,[]);saved=persistent[name]
        assert len(live)==len(saved),(name,len(live),len(saved))
        for tag,row in zip(live,saved):
            assert len(tag)==14 and int(tag[0]) in [0,1,2]
            assert tag[4]==row[0] and tag[7]==row[3],(name,'ordered actual hit identifier/barcode')
            assert abs(tag[5]-row[1])<=1.1e-5+abs(tag[5])*2e-7
        validation.append(dict(collection=name,hits=len(saved),
            max_energy_delta_MeV=max((abs(a[5]-b[1]) for a,b in zip(live,saved)),default=0),
            max_time_delta_ns=max((abs(a[6]-b[2]) for a,b in zip(live,saved)),default=0),
            max_position_delta_mm=max((abs(a[8+j]-b[4+j]) for a,b in zip(live,saved) for j in range(6)),default=0),
            mapping='same index,cardinality,ID/barcode;original converter preserves order;time/position are compressed,not required equal',
            categories={str(c):sum(int(a[0])==c for a in live) for c in range(3)}))
    if index!=50:
        run('source_control',[sys.executable,str(ROOT/'ml/stage142_control_general.py'),str(index)],ROOT)
    report.update(successful=True,frame50_sensitive_snapshot_exact=True if index==50 else None,ordered_hit_validation=validation,
        wall_s=time.perf_counter()-tick,new_independent_nu=0,new_energy_fits=0,
        scope='ancestry instrumentation only;needs nativeDAQ total/sourceanalog closure before extra parents')
    (OUT/('preflight_report.json' if index==50 else f'parent_{index}_report.json')).write_text(json.dumps(report,indent=2)+'\n')
    shutil.rmtree(work);print(report,flush=True)
    return report

def main():
    phase=sys.argv[1]
    if phase=='preflight':
        plan=json.loads((OUT/'protocol.json').read_text());worker(plan['preflight_index'])
    else:
        import concurrent.futures
        assert phase=='pilot'
        admission=json.loads((OUT/'pilot_admission.json').read_text());assert admission['admitted']
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            reports=list(pool.map(worker,admission['indices']))
        (OUT/'pilot_results.json').write_text(json.dumps([dict(index=r['case']['frame_index'],successful=r['successful'],wall_s=r['wall_s']) for r in reports],indent=2)+'\n')

if __name__=='__main__':main()
