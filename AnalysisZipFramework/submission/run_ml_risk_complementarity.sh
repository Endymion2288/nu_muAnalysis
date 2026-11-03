#!/usr/bin/env bash
set -eo pipefail
stage78_job="$1"
case "$stage78_job" in fold0|fold1|fold2|final) ;; *) exit 2;; esac
stage78_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_risk_complementarity.XXXXXX")
trap 'rm -rf "$stage78_scratch"' EXIT
tar -xzf energy-ml-risk-complementarity-stage78.tar.gz -C "$stage78_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage78_status=0
mkdir -p "$stage78_scratch/workbook/stage78_energy_ml/$stage78_job"
/usr/bin/time -f 'wall_s=%e user_s=%U system_s=%S maxRSS_KiB=%M' -o "$stage78_scratch/workbook/stage78_energy_ml/$stage78_job/worker.time" \
    timeout --signal=TERM --kill-after=10 3550 python -u "$stage78_scratch/ml/fit_risk_complementarity.py" --job "$stage78_job" || stage78_status=$?
stage78_items=("workbook/stage78_energy_ml/$stage78_job")
if [ -d "$stage78_scratch/ml/artifacts/stage78/$stage78_job" ]; then stage78_items+=("ml/artifacts/stage78/$stage78_job"); fi
tar -czf "$stage78_scratch/results.tar.gz" -C "$stage78_scratch" "${stage78_items[@]}"
xrdcp --silent "$stage78_scratch/results.tar.gz" \
    "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage78/$stage78_job.tar.gz"
exit "$stage78_status"
