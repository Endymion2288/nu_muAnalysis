#!/usr/bin/env bash
set -eo pipefail
stage126_batch="$1"
stage126_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage126.XXXXXX")
trap 'rm -rf "$stage126_scratch"' EXIT
tar -xzf energy-ml-stage126.tar.gz -C "$stage126_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 ROOT_RDF_SNAPSHOT_INFO=0
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
cd "$stage126_scratch"
mkdir -p ntuples/energy_ml_stage126
/usr/bin/time -v -o "workbook/stage126_energy_ml/batch_${stage126_batch}.time" python -u ml/stage126_radius.py --batch "$stage126_batch" --workers 4
python - "$stage126_batch" <<'PY'
import sys,tarfile
from pathlib import Path
batch=sys.argv[1]
with tarfile.open('result.tar.gz','w:gz',compresslevel=1) as t:
    for p in Path('ntuples/energy_ml_stage126').glob('source_*.npz'):t.add(p,arcname=str(p))
    for p in Path('workbook/stage126_energy_ml').glob(f'batch_{batch}.*'):t.add(p,arcname=str(p))
PY
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage126/batch_${stage126_batch}.tar.gz"
