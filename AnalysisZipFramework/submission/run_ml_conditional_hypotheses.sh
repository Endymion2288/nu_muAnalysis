#!/usr/bin/env bash
set -eo pipefail
stage74_job="$1"
case "$stage74_job" in fold0|fold1|fold2|final) ;; *) exit 2;; esac
stage74_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_hypotheses.XXXXXX")
trap 'rm -rf "$stage74_scratch"' EXIT
tar -xzf energy-ml-hypotheses-stage74.tar.gz -C "$stage74_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage74_status=0
mkdir -p "$stage74_scratch/workbook/stage74_energy_ml/$stage74_job"
/usr/bin/time -f 'wall_s=%e user_s=%U system_s=%S maxRSS_KiB=%M' -o "$stage74_scratch/workbook/stage74_energy_ml/$stage74_job/worker.time" \
    timeout --signal=TERM --kill-after=10 1750 python -u "$stage74_scratch/ml/fit_conditional_hypotheses.py" --job "$stage74_job" || stage74_status=$?
stage74_items=("workbook/stage74_energy_ml/$stage74_job")
if [ -d "$stage74_scratch/ml/artifacts/stage74/$stage74_job" ]; then stage74_items+=("ml/artifacts/stage74/$stage74_job"); fi
tar -czf "$stage74_scratch/results.tar.gz" -C "$stage74_scratch" "${stage74_items[@]}"
xrdcp --silent "$stage74_scratch/results.tar.gz" \
    "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage74/$stage74_job.tar.gz"
exit "$stage74_status"
