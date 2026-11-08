"""Exact original11, G4-only, same read-only observer and ordered HITS."""
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
OUT = ROOT / 'workbook/stage178_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage178'

def worker(index):
    with gzip.open(ROOT / 'ntuples/energy_ml_stage131/production_cases.json.gz', 'rt') as stream:
        case = next(r for r in json.load(stream) if r['frame_index'] == index)
    with gzip.open(ROOT / 'ntuples/energy_ml_stage131/parent_evidence.json.gz', 'rt') as stream:
        old = next(r['reports'] for r in json.load(stream) if r['index'] == index)
    assert case['role'] == 1
    work = ROOT / f'chain_{index}'
    work.mkdir()
    env = os.environ.copy()
    env['NU_MU_STAGE176_SEED'] = str(case['seed'])
    for k, v in DATASETS.items():
        env[k] = '/cvmfs/geant4.cern.ch/share/data/' + v
    tick = time.perf_counter()
    report = dict(index=index, case=case, steps=[], successful=False)
    def run(name, command):
        start = time.perf_counter()
        log = OUT / f'parent_{index}_{name}.log'
        with log.open('w') as stream:
            r = subprocess.run(['/usr/bin/time', '-v', '-o', str(OUT / f'parent_{index}_{name}_time.txt'), *command],
                cwd=work, env=env, stdout=stream, stderr=subprocess.STDOUT)
        report['steps'].append(dict(name=name, command=command, returncode=r.returncode, wall_s=time.perf_counter()-start))
        (OUT / f'parent_{index}_report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(index, name, r.returncode, flush=True)
        if r.returncode:
            print(log.read_text()[-6000:], flush=True)
            raise RuntimeError((index, name, r.returncode))
    hits = f'FaserMC-Stage131Nu-990131-{index:05d}-stage131-HITS.root'
    run('sim', [sys.executable, str(ROOT / 'ml/stage176_simulate.py'), case['EVNT'], hits,
        '--geom', 'TI12MC04', '--G4_phys', 'FTFP_BERT', '--skip', str(case['entry']), '-n', '1'])
    raw = json.loads((work / 'lineage.jsonl').read_text().strip())
    for key, value in old['summary']['lineage'].items():
        assert raw[key] == value, (index, key, 'legacy mismatch')
    with gzip.open(CACHE / f'parent_{index}_lineage.json.gz', 'wt') as stream:
        json.dump(raw, stream, separators=(',', ':'))
    snapshot = CACHE / f'parent_{index}_qa_hits.json.gz'
    run('hitscheck', [sys.executable, str(ROOT / 'ml/stage131_hitscheck.py'), str(work / hits), str(work / 'lineage.jsonl'),
        str(OUT / f'parent_{index}_hitscheck.json'), 'before', str(snapshot)])
    with gzip.open(snapshot, 'rt') as stream:
        saved = json.load(stream)
    for name, rows in raw['daq_hits'].items():
        assert len(rows) == len(saved[name]) == len(raw['daq_birth_groups'][name])
        for live, persist in zip(rows, saved[name]):
            assert len(live) == 14 and live[4] == persist[0] and live[7] == persist[3]
            assert abs(live[5]-persist[1]) <= 1.1e-5 + abs(live[5])*2e-7
    command = ['env', '-i', 'PATH=/usr/bin:/bin', 'HOME=' + os.environ['HOME'], 'USER=' + os.environ.get('USER', 'xcheng'),
        'PYTHONNOUSERSITE=1', 'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'bash', '-c',
        'source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh\ncd "$1"\npython ml/stage178_classify.py "$2"',
        'bash', str(ROOT), str(index)]
    run('classify', command)
    report.update(successful=True, legacy_fields_exact=True, ordered_hits_exact=True,
        wall_s=time.perf_counter()-tick, scratch_ROOT_B=sum(p.stat().st_size for p in work.glob('*.root')),
        digitization=False, reconstruction=False, energy_fits=0, new_independent_nu=0)
    (OUT / f'parent_{index}_report.json').write_text(json.dumps(report, indent=2) + '\n')
    shutil.rmtree(work)
    return dict(index=index, successful=True, wall_s=report['wall_s'])

if __name__ == '__main__':
    p = json.loads((OUT / 'protocol.json').read_text())
    assert json.loads((OUT / 'admission.json').read_text())['admitted']
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(worker, p['replay_indices']))
    (OUT / 'replay_summary.json').write_text(json.dumps(dict(passed=True, parents=results, energy_fits=0,
        new_independent_nu=0, overall_complete=False), indent=2) + '\n')
