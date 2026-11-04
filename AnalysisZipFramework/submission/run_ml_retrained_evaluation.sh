#!/usr/bin/env bash
set -eo pipefail
evaluation_role=$1
evaluation_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_retrain92_eval.XXXXXX")
trap 'rm -rf "$evaluation_scratch"' EXIT
tar -xzf "energy-ml-retrain-stage92-${evaluation_role}.tar.gz" -C "$evaluation_scratch"
mkdir -p "$evaluation_scratch/workbook/stage92_energy_ml/$evaluation_role"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
ulimit -S -t 10500
ulimit -H -t 10600
evaluation_status=0
/usr/bin/time -v -o "$evaluation_scratch/workbook/stage92_energy_ml/$evaluation_role/job.time" \
    timeout --signal=TERM --kill-after=10 10700 python -u "$evaluation_scratch/ml/evaluate_retrained_posterior.py" worker --role "$evaluation_role" || evaluation_status=$?
evaluation_items=("workbook/stage92_energy_ml/$evaluation_role")
if [[ -f "$evaluation_scratch/ntuples/energy_ml_stage92/predictions_${evaluation_role}.npz" ]]; then
    evaluation_items+=("ntuples/energy_ml_stage92/predictions_${evaluation_role}.npz")
fi
tar -czf "$evaluation_scratch/result.tar.gz" -C "$evaluation_scratch" "${evaluation_items[@]}"
xrdcp --silent "$evaluation_scratch/result.tar.gz" "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage92/result_${evaluation_role}.tar.gz"
exit "$evaluation_status"
