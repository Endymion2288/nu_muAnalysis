#!/usr/bin/env bash
set -eo pipefail
stage143_index=$1
stage143_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage143.XXXXXX")
tar -xzf energy-ml-stage143.tar.gz -C "$stage143_work"
cd "$stage143_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 NU_MU_SKIP_LCG=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export NU_MU_RESPONSE_STAGE=143
mkdir -p workbook/stage143_energy_ml ntuples/energy_ml_stage143
touch .stage143_start
source setup_env.sh
nu_mu_official_setup "$stage143_work/runtime"
mkdir observer
tar -xzf software/stage142/observer-runtime.tar.gz -C observer
export LD_LIBRARY_PATH="$stage143_work/observer/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="$stage143_work/observer/python:${PYTHONPATH:-}"
export DATAPATH="$stage143_work/observer/lib:${DATAPATH:-}"
stage143_status=0
/usr/bin/time -v -o "workbook/stage143_energy_ml/parent_${stage143_index}_time.txt" python -u ml/stage143_response.py "$stage143_index" || stage143_status=$?
printf '%s\n' "$stage143_status" > "workbook/stage143_energy_ml/parent_${stage143_index}_exitcode.txt"
find workbook/stage143_energy_ml ntuples/energy_ml_stage143 -type f -newer .stage143_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage143/parent_${stage143_index}_result.tar.gz"
exit "$stage143_status"
