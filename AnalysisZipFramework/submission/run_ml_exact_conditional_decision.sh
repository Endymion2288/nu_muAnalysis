#!/usr/bin/env bash
set -eo pipefail
stage76_job="$1"
case "$stage76_job" in fold0|fold1|fold2|final) ;; *) exit 2;; esac
stage76_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_exact_decision.XXXXXX")
trap 'rm -rf "$stage76_scratch"' EXIT
tar -xzf energy-ml-exact-decision-stage76.tar.gz -C "$stage76_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage76_status=0
mkdir -p "$stage76_scratch/workbook/stage76_energy_ml/$stage76_job"
/usr/bin/time -f 'wall_s=%e user_s=%U system_s=%S maxRSS_KiB=%M' -o "$stage76_scratch/workbook/stage76_energy_ml/$stage76_job/worker.time" \
    timeout --signal=TERM --kill-after=10 1750 python -u "$stage76_scratch/ml/run_exact_conditional_decision.py" --job "$stage76_job" || stage76_status=$?
stage76_items=("workbook/stage76_energy_ml/$stage76_job")
if [ -d "$stage76_scratch/ml/artifacts/stage76/$stage76_job" ]; then stage76_items+=("ml/artifacts/stage76/$stage76_job"); fi
tar -czf "$stage76_scratch/results.tar.gz" -C "$stage76_scratch" "${stage76_items[@]}"
xrdcp --silent "$stage76_scratch/results.tar.gz" \
    "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage76/$stage76_job.tar.gz"
exit "$stage76_status"
