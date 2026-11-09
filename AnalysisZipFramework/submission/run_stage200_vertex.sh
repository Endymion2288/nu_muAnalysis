#!/usr/bin/env bash
set -eo pipefail
vertex200_batch="$1"
vertex200_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_vertex200.XXXXXX")
trap 'rm -rf "$vertex200_scratch"' EXIT
tar -xzf vertex-stage200.tar.gz -C "$vertex200_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 ROOT_RDF_SNAPSHOT_INFO=0
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
cd "$vertex200_scratch"
mkdir -p ntuples/vertex_stage200
/usr/bin/time -v -o "workbook/stage200_vertex/batch_${vertex200_batch}.time" python -u ml/stage200_vertex.py --batch "$vertex200_batch" --workers 4
python - "$vertex200_batch" <<'PY'
import sys
import tarfile
from pathlib import Path
batch = sys.argv[1]
with tarfile.open('result.tar.gz', 'w:gz', compresslevel=1) as archive:
    for path in [Path(f'ntuples/vertex_stage200/batch_{batch}.npz'),
                 Path(f'workbook/stage200_vertex/batch_{batch}.json'),
                 Path(f'workbook/stage200_vertex/batch_{batch}.time')]:
        archive.add(path, arcname=str(path))
PY
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/vertex_stage200/batch_${vertex200_batch}.tar.gz"
