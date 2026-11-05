"""Include all worker/native descendants in the actual Stage115 CPU budget."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from stage113_supervise import cpu_tree

OUT=Path(__file__).resolve().parents[1]/'workbook/stage115_energy_ml'


def main():
    start=time.monotonic();peak=0.;maxproc=0;stop=None
    child=subprocess.Popen([sys.executable,'-u','ml/stage115_run.py'],start_new_session=True)
    while child.poll() is None:
        value,n=cpu_tree(os.getpid());peak=max(peak,value);maxproc=max(maxproc,n)
        if value>=1740 or time.monotonic()-start>=840:
            stop='CPU1740s reserve' if value>=1740 else 'wall840s reserve'
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
        maximum_observed_process_count=maxproc,CPU_stop_threshold_s=1740,wall_stop_threshold_s=840,
        method='own plus reaped-child CPU over live descendant tree; original Stage113 counter reused; GNU external total authoritative')
    (OUT/'watchdog.json').write_text(json.dumps(record,indent=2)+'\n')
    return 124 if stop else code


if __name__=='__main__': raise SystemExit(main())
