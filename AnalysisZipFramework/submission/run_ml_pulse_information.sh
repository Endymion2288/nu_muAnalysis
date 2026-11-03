#!/usr/bin/env bash
set -eo pipefail
stage79_job="$1"
case "$stage79_job" in 0|1|2|3) ;; *) exit 2;; esac
stage79_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_pulse_information.XXXXXX")
trap 'rm -rf "$stage79_scratch"' EXIT
tar -xzf energy-ml-pulse-information-stage79.tar.gz -C "$stage79_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage79_status=0
mkdir -p "$stage79_scratch/ntuples/energy_ml_stage79"
/usr/bin/time -f 'wall_s=%e user_s=%U system_s=%S maxRSS_KiB=%M' -o "$stage79_scratch/workbook/stage79_energy_ml/worker${stage79_job}.time" \
    timeout --signal=TERM --kill-after=10 3500 python -u "$stage79_scratch/ml/pulse_information_audit.py" extract --job "$stage79_job" || stage79_status=$?
stage79_items=("workbook/stage79_energy_ml/worker${stage79_job}.time")
if [ -f "$stage79_scratch/ntuples/energy_ml_stage79/part${stage79_job}.npz" ]; then
    stage79_items+=("ntuples/energy_ml_stage79/part${stage79_job}.npz" "workbook/stage79_energy_ml/extraction${stage79_job}.json")
fi
tar -czf "$stage79_scratch/results.tar.gz" -C "$stage79_scratch" "${stage79_items[@]}"
xrdcp --silent "$stage79_scratch/results.tar.gz" \
    "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage79/job${stage79_job}.tar.gz"
exit "$stage79_status"
