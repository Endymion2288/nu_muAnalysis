#!/usr/bin/env bash
set -eo pipefail
stage127_batch="$1"
stage127_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage127.XXXXXX")
trap 'rm -rf "$stage127_scratch"' EXIT
tar -xzf energy-ml-stage127-coordinates.tar.gz -C "$stage127_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
cd "$stage127_scratch"
/usr/bin/time -v -o "workbook/stage127_energy_ml/coordinates_${stage127_batch}.time" python -u ml/stage127_coordinates.py --batch "$stage127_batch"
python - "$stage127_batch" <<'PY'
import tarfile,sys
from pathlib import Path
batch=sys.argv[1]
with tarfile.open('result.tar.gz','w:gz',compresslevel=1) as t:
    for p in [Path(f'ntuples/energy_ml_stage127/coordinates_{batch}.npz'),Path(f'workbook/stage127_energy_ml/coordinates_{batch}.json'),Path(f'workbook/stage127_energy_ml/coordinates_{batch}.time')]:t.add(p,arcname=str(p))
PY
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage127/coordinates_${stage127_batch}.tar.gz"
