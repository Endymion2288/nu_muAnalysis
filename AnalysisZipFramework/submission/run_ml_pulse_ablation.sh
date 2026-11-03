#!/usr/bin/env bash
set -eo pipefail
stage80_mode="$1"
stage80_job="$2"
case "$stage80_mode:$stage80_job" in extract:[0-3]|fit:fold[0-2]|fit:final) ;; *) exit 2;; esac
stage80_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_pulse_ablation.XXXXXX")
trap 'rm -rf "$stage80_scratch"' EXIT
tar -xzf "energy-ml-pulse-ablation-stage80-${stage80_mode}.tar.gz" -C "$stage80_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage80_status=0
stage80_items=()
if [ "$stage80_mode" = extract ]; then
    stage80_time="workbook/stage80_energy_ml/extract${stage80_job}.time"
    /usr/bin/time -f 'wall_s=%e user_s=%U system_s=%S maxRSS_KiB=%M' -o "$stage80_scratch/$stage80_time" \
        timeout --signal=TERM --kill-after=10 1750 python -u "$stage80_scratch/ml/extract_pulse_ablation.py" --job "$stage80_job" || stage80_status=$?
    stage80_items+=("$stage80_time")
    if [ -f "$stage80_scratch/ntuples/energy_ml_stage80/extract${stage80_job}.npz" ]; then
        stage80_items+=("ntuples/energy_ml_stage80/extract${stage80_job}.npz" "workbook/stage80_energy_ml/extract${stage80_job}.json")
    fi
else
    mkdir -p "$stage80_scratch/workbook/stage80_energy_ml/$stage80_job"
    stage80_items+=("workbook/stage80_energy_ml/$stage80_job")
    /usr/bin/time -f 'wall_s=%e user_s=%U system_s=%S maxRSS_KiB=%M' -o "$stage80_scratch/workbook/stage80_energy_ml/$stage80_job/worker.time" \
        timeout --signal=TERM --kill-after=10 1750 python -u "$stage80_scratch/ml/fit_pulse_ablation.py" --job "$stage80_job" || stage80_status=$?
    if [ -d "$stage80_scratch/ml/artifacts/stage80/$stage80_job" ]; then stage80_items+=("ml/artifacts/stage80/$stage80_job"); fi
fi
tar -czf "$stage80_scratch/results.tar.gz" -C "$stage80_scratch" "${stage80_items[@]}"
xrdcp --silent "$stage80_scratch/results.tar.gz" \
    "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage80/${stage80_mode}_${stage80_job}.tar.gz"
exit "$stage80_status"
