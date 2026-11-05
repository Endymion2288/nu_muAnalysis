#!/usr/bin/env bash
set -eo pipefail
stage119_phase=$1
stage119_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage119.XXXXXX")
trap 'rm -rf "$stage119_scratch"' EXIT
tar -xzf "energy-ml-stage119-${stage119_phase}.tar.gz" -C "$stage119_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
if [[ "$stage119_phase" == native || "$stage119_phase" == recoqa || "$stage119_phase" == sparseqa || "$stage119_phase" == sparseqa2 || "$stage119_phase" == sparseqa3 || "$stage119_phase" == pythiaqa || "$stage119_phase" == window || "$stage119_phase" == window2 || "$stage119_phase" == window3 || "$stage119_phase" == window4 || "$stage119_phase" == pythiasparseqa2 || "$stage119_phase" == pythiasparseqa || "$stage119_phase" == pythiapilot ]]; then
    export NU_MU_SKIP_LCG=1
    source "$stage119_scratch/setup_env.sh"
    nu_mu_official_setup "$stage119_scratch/runtime"
else
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
fi
cd "$stage119_scratch"
mkdir -p ntuples/energy_ml_stage119 ml/artifacts/stage119
stage119_status=0
/usr/bin/time -v -o "workbook/stage119_energy_ml/${stage119_phase}_time.txt" timeout --signal=TERM --kill-after=10 3500 python -u "ml/stage119_${stage119_phase}.py" || stage119_status=$?
python - <<'PY'
import tarfile
from pathlib import Path
with tarfile.open('result.tar.gz','w:gz',compresslevel=1) as t:
    for base in ['workbook/stage119_energy_ml','ntuples/energy_ml_stage119','ml/artifacts/stage119']:
        if Path(base).exists():
            for p in sorted(Path(base).iterdir()):
                if p.is_file():t.add(p,arcname=str(p))
PY
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage119/${stage119_phase}_result.tar.gz"
exit "$stage119_status"
