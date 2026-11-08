"""Bounded pilot or four independent chains on the four allocated CPU cores."""
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from pathlib import Path

root=Path.cwd(); phase=sys.argv[1]
tick=time.perf_counter()
if phase=='pilot':
    tasks=[('pilot_seq',0,128),('pilot_suffix',64,64)]
else:
    group=int(phase.removeprefix('batch_'))
    assert 0<=group<16
    tasks=[(f'chunk_{i:02d}',64*i,64) for i in range(4*group,4*group+4)]


def run(task):
    name,begin,count=task
    cmd=[sys.executable,str(root/'ml/stage157_pipeline.py'),name,str(begin),str(count)]
    return dict(label=name,begin=begin,N=count,returncode=subprocess.run(cmd,check=False).returncode)


if phase=='pilot':
    results=[]
    for task in tasks:
        result=run(task);results.append(result)
        if result['returncode']:break
else:
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results=list(executor.map(run,tasks))
report=dict(phase=phase,tasks=results,wall_s=time.perf_counter()-tick,
    processes_at_once=1 if phase=='pilot' else 4,requested_CPU_cores=int(os.environ.get('_CONDOR_NPROCS','4')),
    passed=len(results)==len(tasks) and all(r['returncode']==0 for r in results))
(root/f'workbook/stage157_energy_ml/{phase}_driver.json').write_text(json.dumps(report,indent=2)+'\n')
assert report['passed'],report
