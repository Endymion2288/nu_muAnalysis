#!/usr/bin/env bash
set -eo pipefail
stage199_phase=$1
stage199_indices=$2
stage199_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage199_batch.XXXXXX")
trap 'rm -rf "$stage199_work"' EXIT
tar -xzf energy-ml-stage199.tar.gz -C "$stage199_work"
export NU_MU_STAGE199_CODE="$stage199_work"
export NU_MU_STAGE199_RUNTIME="$stage199_work/runtime"
mkdir -p "$NU_MU_STAGE199_RUNTIME"
tar -xzf /eos/user/x/xcheng/FASER/nu_muAnalysis/software/calypso-master-d32b0ff3-el9-gcc13.tar.gz -C "$NU_MU_STAGE199_RUNTIME"
python3 - "$stage199_phase" "$stage199_indices" <<'PY'
import concurrent.futures,json,os,subprocess,sys,time
from pathlib import Path
tick=time.monotonic()
def run(i):
    rc=subprocess.call(['bash',str(Path(os.environ['NU_MU_STAGE199_CODE'])/'AnalysisZipFramework/submission/run_ml_stage199_source.sh'),str(i),sys.argv[1]])
    return dict(index=i,returncode=rc)
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    rows=list(pool.map(run,map(int,sys.argv[2].split(','))))
print(json.dumps(dict(results=rows,wall_s=time.monotonic()-tick)),flush=True)
sys.exit(int(any(r['returncode'] for r in rows)))
PY
