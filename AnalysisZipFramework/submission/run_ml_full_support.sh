#!/usr/bin/env bash
set -eo pipefail
full_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_full84.XXXXXX")
trap 'rm -rf "$full_scratch"' EXIT
tar -xzf energy-ml-full-support-stage84.tar.gz -C "$full_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
ulimit -S -t 1080
ulimit -H -t 1100
full_status=0
/usr/bin/time -v -o "$full_scratch/workbook/stage84_energy_ml/worker.time" \
    timeout --signal=TERM --kill-after=10 1100 python -u "$full_scratch/ml/full_support_fit.py" fit || full_status=$?
full_items=(workbook/stage84_energy_ml)
if [[ -d "$full_scratch/ml/artifacts/stage84" ]]; then full_items+=(ml/artifacts/stage84); fi
tar -czf "$full_scratch/results.tar.gz" -C "$full_scratch" "${full_items[@]}"
xrdcp --silent "$full_scratch/results.tar.gz" "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage84/result.tar.gz"
exit "$full_status"
