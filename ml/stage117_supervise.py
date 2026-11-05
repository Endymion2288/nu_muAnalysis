"""Include all worker/native descendants in the actual Stage117 CPU budget."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from stage113_supervise import cpu_tree

OUT=Path(__file__).resolve().parents[1]/'workbook/stage117_energy_ml'


def main():
    start=time.monotonic();peak=0.;maxproc=0;stop=None
    child=subprocess.Popen([sys.executable,'-u','ml/stage117_run.py'],start_new_session=True)
    while child.poll() is None:
        value,n=cpu_tree(os.getpid());peak=max(peak,value);maxproc=max(maxproc,n)
        if value>=6900 or time.monotonic()-start>=3450:
            stop='CPU6900s reserve' if value>=6900 else 'wall3450s reserve'
            os.killpg(child.pid,signal.SIGTERM)
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: pass
            try: os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            break
        time.sleep(.5)
    code=child.wait();value,_=cpu_tree(os.getpid())
    record=dict(passed=code==0 and stop is None,worker_exit=code,stop=stop,
        monitored_CPU_s=max(peak,value),monitored_wall_s=time.monotonic()-start,
        maximum_observed_process_count=maxproc,CPU_stop_threshold_s=6900,wall_stop_threshold_s=3450,
        method='own plus reaped-child CPU over live descendant tree; original Stage113 counter reused; GNU external total authoritative')
    (OUT/'watchdog.json').write_text(json.dumps(record,indent=2)+'\n')
    return 124 if stop else code


if __name__=='__main__': raise SystemExit(main())
