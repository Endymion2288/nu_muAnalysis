#!/usr/bin/env bash
set -eo pipefail
stage112_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage112.XXXXXX")
trap 'rm -rf "$stage112_scratch"' EXIT
tar -xzf energy-ml-stage112.tar.gz -C "$stage112_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 ROOT_RDF_SNAPSHOT_INFO=0
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
cd "$stage112_scratch"
export ROOT_INCLUDE_PATH="$stage112_scratch/AnalysisZipFramework/include:${ROOT_INCLUDE_PATH:-}"
mkdir -p workbook/stage112_energy_ml
stage112_status=0
/usr/bin/time -v -o workbook/stage112_energy_ml/time.txt timeout --signal=TERM --kill-after=5 850 python -u ml/stage112_audit.py || stage112_status=$?
python - <<'PY'
import tarfile
from pathlib import Path
with tarfile.open('result.tar.gz', 'w:gz', compresslevel=1) as t:
    for p in sorted(Path('workbook/stage112_energy_ml').iterdir()):
        if p.is_file(): t.add(p, arcname=str(p))
PY
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage112/result.tar.gz
exit "$stage112_status"
