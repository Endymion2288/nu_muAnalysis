#!/usr/bin/env bash
set -eo pipefail
curve_arm=$1
curve_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_curve82.XXXXXX")
trap 'rm -rf "$curve_scratch"' EXIT
tar -xzf energy-ml-k-curve-stage82.tar.gz -C "$curve_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
# The lifted restriction concerns K production; retain the frozen fit budget.
ulimit -S -t 880
ulimit -H -t 900
curve_status=0
/usr/bin/time -v -o "$curve_scratch/workbook/stage82_energy_ml/worker_$curve_arm.time" \
    timeout --signal=TERM 1750 python -u "$curve_scratch/ml/k_support_curve.py" fit --arm "$curve_arm" || curve_status=$?
curve_items=(workbook/stage82_energy_ml)
if [[ -d "$curve_scratch/ml/artifacts/stage82/$curve_arm" ]]; then curve_items+=("ml/artifacts/stage82/$curve_arm"); fi
tar -czf "$curve_scratch/results.tar.gz" -C "$curve_scratch" "${curve_items[@]}"
xrdcp --silent "$curve_scratch/results.tar.gz" "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage82/curve_$curve_arm.tar.gz"
exit "$curve_status"
