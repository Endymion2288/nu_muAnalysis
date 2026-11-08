"""One fixed original-entry slice; each Athena process remains independent."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

root = Path.cwd()
label, begin, count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
phase = 'chains/'+label
out, cache = root/'workbook/stage157_energy_ml'/phase, root/'ntuples/energy_ml_stage157'/phase
out.mkdir(parents=True, exist_ok=True); cache.mkdir(parents=True, exist_ok=True)
plan = json.loads((out.parent.parent/'protocol.json').read_text())
work = root/('chain_'+label)
work.mkdir()
tick, steps = time.perf_counter(), []
env = os.environ.copy(); env['NU_MU_CHAIN_BEGIN'] = str(begin)


def run(name, command):
    start = time.perf_counter()
    with (out/(name+'.log')).open('w') as stream:
        result = subprocess.run(['/usr/bin/time','-v','-o',str(out/(name+'_time.txt'))]+command,
            cwd=work, env=env, stdout=stream, stderr=subprocess.STDOUT)
    steps.append(dict(name=name, command=command, returncode=result.returncode, wall_s=time.perf_counter()-start))
    (out/'pipeline.json').write_text(json.dumps(dict(label=label, begin=begin, N=count, steps=steps,
        wall_s=time.perf_counter()-tick, successful=False), indent=2)+'\n')
    print(label, name, result.returncode, steps[-1]['wall_s'], flush=True)
    if result.returncode:
        print((out/(name+'.log')).read_text()[-10000:], flush=True)
        raise SystemExit(result.returncode)
    size = sum(p.stat().st_size for p in work.glob('*.root'))
    assert size <= plan['resources']['temporary_ROOT_bytes_per_job_cap']//4, size
    return size


stem = Path(plan['HITS']).stem.removesuffix('-HITS')
rdo, rec = work/(stem+'-RDO.root'), work/(stem+'-xAOD.root')
run('digi',[sys.executable,str(root/'ml/stage157_digitize.py'),plan['HITS'],str(count),str(out/'seeds.json')])
run('reco',[sys.executable,str(root/'ml/stage149_reco.py'),str(rdo),str(count),str(out/'reco_timing.json')])
peak = run('native',[sys.executable,str(root/'ml/stage157_native.py'),str(rec),str(count),str(cache/'native.json.gz'),
    str(work/'ntuple.root'),str(out/'schema.json')])
run('extract',['env','-i','PATH=/usr/bin:/bin','HOME='+os.environ['HOME'],'USER='+os.environ.get('USER','xcheng'),
    'PYTHONNOUSERSITE=1','NU_MU_NATIVE_CONTROL_STAGE=157',f'NU_MU_CHAIN_BEGIN={begin}',
    'OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','bash','-c',
    'source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh\npython "$1/ml/stage157_extract.py" "$1" "$2" "$3"',
    'bash',str(root),phase,str(work/'ntuple.root')])
deleted=[]
for path in work.glob('*.root'):
    deleted.append(dict(name=path.name,bytes=path.stat().st_size));path.unlink()
report=json.loads((out/'pipeline.json').read_text())
report.update(successful=True,peak_ROOT_bytes=peak,deleted_ROOT=deleted,wall_s=time.perf_counter()-tick,
    final_event_bytes=sum(p.stat().st_size for p in cache.glob('*')),intermediate_ROOT_retained=False)
(out/'pipeline.json').write_text(json.dumps(report,indent=2)+'\n')
