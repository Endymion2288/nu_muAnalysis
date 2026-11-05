"""Outer process timer usable in Condor and GPU containers without GNU time."""
import json
import resource
import subprocess
import sys
import time
from pathlib import Path
mode=sys.argv[1]
if mode=='qa_extract':cmd=['ml/stage107_extract.py',mode]
elif mode=='qa':cmd=['ml/stage107_qa.py']
else:raise ValueError('Stage107 only permits zero-optimizer QA')
start=time.perf_counter()
result=subprocess.run([sys.executable,'-u',*cmd])
u=resource.getrusage(resource.RUSAGE_CHILDREN)
record=dict(mode=mode,exit_code=result.returncode,wall_s=time.perf_counter()-start,
            CPU_s=u.ru_utime+u.ru_stime,peak_single_process_RSS_KiB=u.ru_maxrss,
            scope='inclusive child plus its descendants, including imports; do not add nested timers')
Path('workbook/stage107_energy_ml/time_'+mode+'.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
sys.exit(result.returncode)
