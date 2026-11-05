"""Outer process timer usable in Condor and GPU containers without GNU time."""
import json
import resource
import subprocess
import sys
import time
from pathlib import Path
mode=sys.argv[1]
if mode.endswith('extract'):cmd=['ml/stage106_geometry.py',mode]
elif mode=='qa':cmd=['ml/stage106_qa.py']
elif mode=='report':cmd=['ml/stage106_report.py']
else:cmd=['ml/stage106_train.py',mode]
start=time.perf_counter()
result=subprocess.run([sys.executable,'-u',*cmd])
u=resource.getrusage(resource.RUSAGE_CHILDREN)
record=dict(mode=mode,exit_code=result.returncode,wall_s=time.perf_counter()-start,
            CPU_s=u.ru_utime+u.ru_stime,peak_single_process_RSS_KiB=u.ru_maxrss,
            scope='inclusive child plus its descendants, including imports; do not add nested timers')
Path('workbook/stage106_energy_ml/time_'+mode+'.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
sys.exit(result.returncode)
