#!/usr/bin/env bash
set -eo pipefail
retrain_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_retrain92.XXXXXX")
trap 'rm -rf "$retrain_scratch"' EXIT
tar -xzf energy-ml-retrain-stage92-fit.tar.gz -C "$retrain_scratch"
mkdir -p "$retrain_scratch/ml/artifacts/stage92" "$retrain_scratch/workbook/stage92_energy_ml"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
ulimit -S -t 7000
ulimit -H -t 7100
retrain_status=0
/usr/bin/time -v -o "$retrain_scratch/workbook/stage92_energy_ml/fit.time" \
    timeout --signal=TERM --kill-after=10 5300 python -u "$retrain_scratch/ml/retrain_accurate_posterior.py" fit-worker || retrain_status=$?
retrain_items=(workbook/stage92_energy_ml ml/artifacts/stage92)
for retrain_file in startup_heads.npz failed_numerics.npz; do
    if [[ -f "$retrain_scratch/ntuples/energy_ml_stage92/$retrain_file" ]]; then
        retrain_items+=("ntuples/energy_ml_stage92/$retrain_file")
    fi
done
tar -czf "$retrain_scratch/result.tar.gz" -C "$retrain_scratch" "${retrain_items[@]}"
xrdcp --silent "$retrain_scratch/result.tar.gz" root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage92/result_fit.tar.gz
exit "$retrain_status"
