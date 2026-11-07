#!/usr/bin/env bash
set -eo pipefail
stage130_phase=$1
stage130_indices=$2
export NU_MU_STAGE130_PACKAGE="$PWD/energy-ml-stage130.tar.gz"
stage130_batch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage130_batch.XXXXXX")
trap 'rm -rf "$stage130_batch"' EXIT
tar -xzf "$NU_MU_STAGE130_PACKAGE" -C "$stage130_batch"
export NU_MU_STAGE130_RUNTIME="$stage130_batch/runtime"
mkdir -p "$NU_MU_STAGE130_RUNTIME"
tar -xzf /eos/user/x/xcheng/FASER/nu_muAnalysis/software/calypso-master-d32b0ff3-el9-gcc13.tar.gz -C "$NU_MU_STAGE130_RUNTIME"
python3 - "$stage130_batch" "$stage130_phase" "$stage130_indices" <<'PY'
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from pathlib import Path

root, phase, text = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
indices = [int(x) for x in text.split(',')]
tick = time.monotonic()
def run(index):
    result = subprocess.run(['bash', str(root / 'AnalysisZipFramework/submission/run_ml_stage130_source.sh'), str(index), phase])
    return dict(index=index, returncode=result.returncode)
with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.environ.get('_CONDOR_REQUEST_CPUS', len(indices)))) as pool:
    results = list(pool.map(run, indices))
print(json.dumps(dict(results=results, wall_s=time.monotonic()-tick)), flush=True)
sys.exit(int(any(r['returncode'] for r in results)))
PY
