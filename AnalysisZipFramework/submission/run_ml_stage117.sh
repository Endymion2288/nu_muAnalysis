#!/usr/bin/env bash
set -eo pipefail
stage117_phase=$1
stage117_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage117.XXXXXX")
trap 'rm -rf "$stage117_scratch"' EXIT
tar -xzf "energy-ml-stage117-${stage117_phase}.tar.gz" -C "$stage117_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
cd "$stage117_scratch"
stage117_status=0
if [[ "$stage117_phase" == probe ]]; then
    /usr/bin/time -v -o workbook/stage117_energy_ml/probe_time.txt timeout 300 python -u ml/stage117_folds.py || stage117_status=$?
else
    /usr/bin/time -v -o workbook/stage117_energy_ml/time.txt timeout --signal=TERM --kill-after=5 3540 python -u ml/stage117_supervise.py || stage117_status=$?
fi
python - <<'PY'
import tarfile
from pathlib import Path
with tarfile.open('result.tar.gz','w:gz',compresslevel=1) as t:
    for base in ['workbook/stage117_energy_ml','ml/artifacts/stage117']:
        if Path(base).exists():
            for p in sorted(Path(base).iterdir()):
                if p.is_file():t.add(p,arcname=str(p))
PY
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage117/${stage117_phase}_result.tar.gz"
exit "$stage117_status"
