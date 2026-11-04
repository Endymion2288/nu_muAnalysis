"""Time one batch subprocess without requiring GNU time in the GPU container."""
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

root=Path(sys.argv[1]);mode=sys.argv[2];out=root/'workbook/stage96_energy_ml'
commands={'extract':[['ml/prepare_candidate_ablation.py','extract','--processes','8']],
          'fit':[['ml/train_candidate_ablation.py','worker']],
          'report':[['ml/report_candidate_ablation.py','--processes','8']]}
start=time.perf_counter();code=0
for cmd in commands[mode]:
    result=subprocess.run([sys.executable,*cmd],cwd=root)
    code=result.returncode
    if code:break
r=resource.getrusage(resource.RUSAGE_CHILDREN)
value=dict(mode=mode,exit_code=code,wall_s=time.perf_counter()-start,CPU_s=r.ru_utime+r.ru_stime,
           max_single_process_RSS_KiB=r.ru_maxrss,scope='outer child scope includes its descendants; nested timings must not be added')
(out/(mode+'_job.json')).write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps(value),flush=True)
sys.exit(code)
