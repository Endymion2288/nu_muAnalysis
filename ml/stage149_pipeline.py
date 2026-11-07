"""Bounded HITS prefix -> official RDO/REC -> compact paired observations."""
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

root = Path.cwd()
stage = int(os.environ.get('NU_MU_NATIVE_CONTROL_STAGE', '149'))
phase = sys.argv[1]
count = 4 if phase == 'pilot' else 64
out = root/f'workbook/stage{stage}_energy_ml'/phase
cache = root/f'ntuples/energy_ml_stage{stage}'/phase
out.mkdir(parents=True, exist_ok=True)
cache.mkdir(parents=True, exist_ok=True)
plan = json.loads((out.parent/'protocol.json').read_text())
work = root/('chain_'+phase)
work.mkdir()
tick = time.perf_counter()
steps = []


def run(name, command):
    start = time.perf_counter()
    with (out/(name+'.log')).open('w') as stream:
        result = subprocess.run(['/usr/bin/time', '-v', '-o', str(out/(name+'_time.txt'))]+command,
                                cwd=work, stdout=stream, stderr=subprocess.STDOUT)
    steps.append(dict(name=name, command=command, returncode=result.returncode, wall_s=time.perf_counter()-start))
    (out/'pipeline.json').write_text(json.dumps(dict(phase=phase, N=count, steps=steps,
        wall_s=time.perf_counter()-tick, successful=False), indent=2)+'\n')
    print('STEP', name, result.returncode, steps[-1]['wall_s'], flush=True)
    if result.returncode:
        print((out/(name+'.log')).read_text()[-10000:], flush=True)
        raise SystemExit(result.returncode)
    files = list(work.glob('*.root'))
    size = sum(f.stat().st_size for f in files)
    assert size <= plan['resources']['temporary_ROOT_bytes_cap'], size
    return size


stem = Path(plan['HITS']).stem.removesuffix('-HITS')
rdo, rec = work/(stem+'-RDO.root'), work/(stem+'-xAOD.root')
run('digi', [sys.executable, str(root/'ml/stage149_digitize.py'), plan['HITS'], str(count), str(out/'seeds.json')])
run('reco', [sys.executable, str(root/'ml/stage149_reco.py'), str(rdo), str(count), str(out/'reco_timing.json')])
peak_size = run('native', [sys.executable, str(root/'ml/stage149_native.py'), str(rec), str(count),
                         str(cache/'native.json.gz'), str(work/'ntuple.root')])
run('extract', ['env', '-i', 'PATH=/usr/bin:/bin', 'HOME='+os.environ['HOME'], 'USER='+os.environ.get('USER', 'xcheng'),
    'PYTHONNOUSERSITE=1', f'NU_MU_NATIVE_CONTROL_STAGE={stage}', 'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'bash', '-c',
    'source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh\npython "$1/ml/stage149_extract.py" "$1" "$2" "$3"',
    'bash', str(root), phase, str(work/'ntuple.root')])
size = sum(f.stat().st_size for f in cache.glob('*'))
assert size <= plan['resources']['final_event_bytes_cap']
deleted = []
for path in work.glob('*.root'):
    deleted.append(dict(name=path.name, bytes=path.stat().st_size))
    path.unlink()
report = json.loads((out/'pipeline.json').read_text())
report.update(successful=True, peak_ROOT_bytes=peak_size, deleted_ROOT=deleted, final_event_bytes=size,
              wall_s=time.perf_counter()-tick, intermediate_ROOT_retained=False)
(out/'pipeline.json').write_text(json.dumps(report, indent=2)+'\n')
