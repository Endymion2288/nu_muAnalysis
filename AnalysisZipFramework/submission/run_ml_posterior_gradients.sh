#!/usr/bin/env bash
set -eo pipefail
gradient_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_gradients90.XXXXXX")
trap 'rm -rf "$gradient_scratch"' EXIT
tar -xzf energy-ml-gradients-stage90.tar.gz -C "$gradient_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
ulimit -S -t 1600
ulimit -H -t 1620
gradient_status=0
/usr/bin/time -v -o "$gradient_scratch/workbook/stage90_energy_ml/job.time" \
    timeout --signal=TERM --kill-after=10 1700 python -u "$gradient_scratch/ml/audit_posterior_gradients.py" worker || gradient_status=$?
gradient_items=(workbook/stage90_energy_ml)
if [[ -f "$gradient_scratch/ntuples/energy_ml_stage90/audit_values.npz" ]]; then
    gradient_items+=(ntuples/energy_ml_stage90/audit_values.npz)
fi
tar -czf "$gradient_scratch/result.tar.gz" -C "$gradient_scratch" "${gradient_items[@]}"
xrdcp --silent "$gradient_scratch/result.tar.gz" root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage90/result.tar.gz
exit "$gradient_status"
