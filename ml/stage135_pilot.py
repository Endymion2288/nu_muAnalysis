"""Minimal new G4 instrumentation pilot; no fit or energy-model forward."""
import concurrent.futures
import gzip
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from stage131_pilot import DATASETS

ROOT = Path.cwd()
OUT = ROOT/'workbook/stage135_energy_ml'
CACHE = ROOT/'ntuples/energy_ml_stage135'

def worker(case, old, noninterference=False):
    index = case['frame_index']
    work = ROOT/f'chain_{index}'
    work.mkdir()
    env = os.environ.copy()
    env['NU_MU_STAGE135_SEED'] = str(case['seed'])
    for key, value in DATASETS.items():
        env[key] = '/cvmfs/geant4.cern.ch/share/data/'+value
    tick = time.perf_counter()
    report = dict(index=index, case=case, successful=False, steps=[])
    def run(name, command):
        start = time.perf_counter()
        log = OUT/f'parent_{index}_{name}.log'
        with log.open('w') as stream:
            result = subprocess.run(['/usr/bin/time', '-v', '-o',
                str(OUT/f'parent_{index}_{name}_time.txt'), *command],
                cwd=work, env=env, stdout=stream, stderr=subprocess.STDOUT)
        report['steps'].append(dict(name=name, command=command,
            returncode=result.returncode, wall_s=time.perf_counter()-start))
        (OUT/f'parent_{index}_report.json').write_text(json.dumps(report, indent=2)+'\n')
        print(index, name, result.returncode, flush=True)
        if result.returncode:
            print(log.read_text()[-7000:], flush=True)
            raise RuntimeError((index, name, result.returncode))
        text=log.read_text()
        if len(text)>14000:
            log.write_text(text[:4000]+'\n[successful log compacted]\n'+text[-10000:])
    # Keep the original filename as well as seed: framework streams can depend
    # on the HITS output filename. Only the observer component changes.
    hits=f'FaserMC-Stage131Nu-990131-{index:05d}-stage131-HITS.root'
    simulate=[sys.executable,str(ROOT/'ml/stage135_simulate.py'),
        case['EVNT'],hits,'--geom','TI12MC04','--G4_phys','FTFP_BERT',
        '--skip',str(case['entry']),'-n','1']
    run('sim',simulate)
    lineage=json.loads((work/'lineage.jsonl').read_text().strip())
    report['lineage']=lineage
    (OUT/f'parent_{index}_report.json').write_text(json.dumps(report,indent=2)+'\n')
    bins=lineage['boundary_bins']
    for r in bins:
        assert len(r)==14 and r[4]>0 and r[5]>=0 and r[6]>=r[5]
    for position,key in [(5,'flow_KE_MeV'),(6,'flow_total_MeV')]:
        actual=sum(r[position] for r in bins)
        expected=lineage[key][1]
        assert abs(actual-expected)<=max(1e-7,abs(expected)*1e-10),(key,actual,expected)
    # Reproducing all old observer fields checks that the exact original G4
    # response/identity was reached. This does not prove new family independence.
    legacy=old['summary']['lineage']
    for key,value in legacy.items():
        assert lineage[key]==value,(index,key,'original replay differs')
    report.update(lineage=lineage, legacy_fields_exact=True,
        original_selected_N=old['selection']['selected_N'],
        bin_KE_and_total_closure=True)
    check=[sys.executable,str(ROOT/'ml/stage131_hitscheck.py'),str(work/hits),
        str(work/'lineage.jsonl'),str(OUT/f'parent_{index}_hitscheck.json')]
    if noninterference:
        check+=['before',str(CACHE/f'parent_{index}_qa_hits.json.gz')]
    run('hitscheck',check)
    if noninterference:
        env['NU_MU_STAGE135_OBSERVER']='0'
        (work/hits).unlink()
        (work/'PoolFileCatalog.xml').unlink(missing_ok=True)
        run('sim_unobserved',simulate)
        run('noninterference',[sys.executable,str(ROOT/'ml/stage131_hitscheck.py'),
            str(work/hits),str(work/'lineage.jsonl'),
            str(OUT/f'parent_{index}_noninterference.json'),'after',
            str(CACHE/f'parent_{index}_qa_hits.json.gz')])
    report.update(successful=True,wall_s=time.perf_counter()-tick,
        scratch_ROOT_logical_B=sum(p.stat().st_size for p in work.glob('*.root')),
        new_independent_neutrinos=0, energy_fits=0, intermediate_ROOT_retained=False)
    (OUT/f'parent_{index}_report.json').write_text(json.dumps(report,indent=2)+'\n')
    shutil.rmtree(work)
    return dict(index=index,successful=True,wall_s=report['wall_s'])

def main():
    phase=sys.argv[1]
    protocol=json.loads((OUT/'pilot_protocol.json').read_text())
    with gzip.open(ROOT/'ntuples/energy_ml_stage131/production_cases.json.gz','rt') as stream:
        cases={r['frame_index']:r for r in json.load(stream)}
    with gzip.open(ROOT/'ntuples/energy_ml_stage131/parent_evidence.json.gz','rt') as stream:
        evidence={r['index']:r['reports'] for r in json.load(stream)}
    indices=[protocol['preflight_index']] if phase=='preflight' else protocol['remaining_indices']
    assert all(cases[i]['role']==1 for i in indices)
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=1 if phase=='preflight' else 4) as pool:
        futures={pool.submit(worker,cases[i],evidence[i],phase=='preflight'):i for i in indices}
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result())
            except Exception as error:
                results.append(dict(index=futures[future],successful=False,error=repr(error)))
    (OUT/f'{phase}_results.json').write_text(json.dumps(results,indent=2)+'\n')
    assert all(r['successful'] for r in results),results

if __name__=='__main__':
    main()
