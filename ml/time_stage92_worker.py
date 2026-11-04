"""Portable outer timer for an unchanged stage92 worker on curated ML images."""
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

worker = Path(sys.argv[1])
start = time.monotonic()
proc = subprocess.Popen([sys.executable, '-u', str(worker), 'fit-worker'])
timed_out = False
try:
    code = proc.wait(timeout=5300)
except subprocess.TimeoutExpired:
    timed_out = True
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    code = 124
usage = resource.getrusage(resource.RUSAGE_CHILDREN)
result = dict(user_CPU_s=usage.ru_utime, system_CPU_s=usage.ru_stime,
              CPU_s=usage.ru_utime+usage.ru_stime, wall_s=time.monotonic()-start,
              peak_RSS_KiB=usage.ru_maxrss, exit_code=code, timed_out=timed_out,
              scope='outer worker subprocess incl imports/initialQA/fit/cal; excludes prior container/CVMFS/preflight startup and OAuth sidecars; no duplicate internal timing')
path = worker.parents[1] / 'workbook/stage92_energy_ml/fit_outer_resources.json'
path.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
print('outer timer', json.dumps(result), flush=True)
sys.exit(code if code >= 0 else 128-code)
