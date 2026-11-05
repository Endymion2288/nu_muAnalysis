#!/usr/bin/env bash
set -eo pipefail
stage115_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage115.XXXXXX")
trap 'rm -rf "$stage115_scratch"' EXIT
tar -xzf energy-ml-stage115.tar.gz -C "$stage115_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
cd "$stage115_scratch"
stage115_status=0
/usr/bin/time -v -o workbook/stage115_energy_ml/time.txt timeout --signal=TERM --kill-after=5 880 python -u ml/stage115_supervise.py || stage115_status=$?
python - <<'PY'
import tarfile
from pathlib import Path
with tarfile.open('result.tar.gz','w:gz',compresslevel=1) as t:
    for base in ['workbook/stage115_energy_ml','ml/artifacts/stage115']:
        if Path(base).exists():
            for p in sorted(Path(base).iterdir()):
                if p.is_file():t.add(p,arcname=str(p))
PY
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage115/result.tar.gz
exit "$stage115_status"
