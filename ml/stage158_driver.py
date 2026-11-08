"""Independent read-only Athena chains in unique scratch directories."""
import concurrent.futures
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

root=Path.cwd();phase=sys.argv[1];out=root/'workbook/stage158_energy_ml';cache=root/'ntuples/energy_ml_stage158'
tick=time.perf_counter()
if phase=='pilot':tasks=['pilot','repeat']
else:
    group=int(phase.removeprefix('batch_'));assert 0<=group<10
    tasks=[f'native_{i:02d}' for i in range(4*group,min(37,4*group+4))]


def run(task):
    work=root/('chain_'+task);work.mkdir()
    (work/'ml').symlink_to(root/'ml',target_is_directory=True)
    (work/'workbook/stage158_energy_ml').mkdir(parents=True)
    (work/'workbook/stage158_energy_ml/protocol.json').symlink_to(out/'protocol.json')
    (work/'workbook/stage124_energy_ml').symlink_to(root/'workbook/stage124_energy_ml',target_is_directory=True)
    (work/'ntuples/energy_ml_stage158').mkdir(parents=True)
    (work/'ntuples/energy_ml_stage119').symlink_to(root/'ntuples/energy_ml_stage119',target_is_directory=True)
    with (out/f'{task}.log').open('w') as stream:
        result=subprocess.run(['/usr/bin/time','-v','-o',str(out/f'{task}_time.txt'),
            sys.executable,str(root/'ml/stage158_native.py'),task],cwd=work,stdout=stream,stderr=subprocess.STDOUT)
    for directory in ['workbook/stage158_energy_ml','ntuples/energy_ml_stage158']:
        for path in (work/directory).glob(task+'*'):
            if path.is_file():shutil.copyfile(path,root/directory/path.name)
    if result.returncode:print((out/f'{task}.log').read_text()[-10000:],flush=True)
    return dict(task=task,returncode=result.returncode,persistent_ROOT_files=[])


if phase=='pilot':
    results=[]
    for task in tasks:
        result=run(task);results.append(result)
        if result['returncode']:break
else:
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:results=list(executor.map(run,tasks))
report=dict(phase=phase,tasks=results,wall_s=time.perf_counter()-tick,max_parallel_chains=1 if phase=='pilot' else len(tasks),
    passed=len(results)==len(tasks) and all(r['returncode']==0 for r in results))
(out/f'{phase}_driver.json').write_text(json.dumps(report,indent=2)+'\n')
assert report['passed'],report
