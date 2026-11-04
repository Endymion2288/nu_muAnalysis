"""Portable stage94 subprocess timer on the curated CERN ML image."""
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

repo=Path(sys.argv[1]);start=time.monotonic()
proc=subprocess.Popen([sys.executable,'-u',str(repo/'ml/compare_energy_architectures.py'),'worker'])
try:code=proc.wait(timeout=7000)
except subprocess.TimeoutExpired:
    proc.terminate()
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()
    code=124
u=resource.getrusage(resource.RUSAGE_CHILDREN)
(repo/'workbook/stage94_energy_ml/worker_outer_resources.json').write_text(json.dumps(dict(exit_code=code,CPU_s=u.ru_utime+u.ru_stime,wall_s=time.monotonic()-start,peak_RSS_KiB=u.ru_maxrss,scope='worker child including imports, reconstruction, all fits/validation/finalforward; not container/CVMFS/OAuth startup'),indent=2)+'\n')
sys.exit(code if code>=0 else 128-code)
