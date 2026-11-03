#!/usr/bin/env bash
set -eo pipefail
stage73_job="$1"
case "$stage73_job" in fold0|fold1|fold2|final) ;; *) exit 2;; esac
stage73_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_reweight.XXXXXX")
trap 'rm -rf "$stage73_scratch"' EXIT
tar -xzf energy-ml-reweight-stage73.tar.gz -C "$stage73_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage73_status=0
mkdir -p "$stage73_scratch/workbook/stage73_energy_ml/$stage73_job"
/usr/bin/time -f 'wall_s=%e user_s=%U system_s=%S maxRSS_KiB=%M' -o "$stage73_scratch/workbook/stage73_energy_ml/$stage73_job/worker.time" \
    timeout --signal=TERM --kill-after=10 1750 python -u "$stage73_scratch/ml/fit_energy_reweight.py" --job "$stage73_job" || stage73_status=$?
stage73_items=("workbook/stage73_energy_ml/$stage73_job")
if [ -d "$stage73_scratch/ml/artifacts/stage73/$stage73_job" ]; then stage73_items+=("ml/artifacts/stage73/$stage73_job"); fi
tar -czf "$stage73_scratch/results.tar.gz" -C "$stage73_scratch" "${stage73_items[@]}"
xrdcp --silent "$stage73_scratch/results.tar.gz" \
    "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage73/$stage73_job.tar.gz"
exit "$stage73_status"
