#!/usr/bin/env bash
set -eo pipefail
stage127_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage127_scan.XXXXXX")
trap 'rm -rf "$stage127_scratch"' EXIT
tar -xzf energy-ml-stage127-scan.tar.gz -C "$stage127_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
cd "$stage127_scratch"
/usr/bin/time -v -o workbook/stage127_energy_ml/scan.time python -u ml/stage127_scan.py
python - <<'PY'
import tarfile
from pathlib import Path
with tarfile.open('result.tar.gz','w:gz',compresslevel=1) as t:
    for p in Path('workbook/stage127_energy_ml').iterdir():
        if p.is_file() and p.name!='protocol.json':t.add(p,arcname=str(p))
PY
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage127/scan_result.tar.gz
