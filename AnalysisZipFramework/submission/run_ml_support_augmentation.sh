#!/usr/bin/env bash
set -eo pipefail
stage71_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_augmentation.XXXXXX")
trap 'rm -rf "$stage71_scratch"' EXIT
tar -xzf energy-ml-support-augmentation-stage71.tar.gz -C "$stage71_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage71_status=0
/usr/bin/time -f 'wall_s=%e user_s=%U system_s=%S maxRSS_KiB=%M' -o "$stage71_scratch/workbook/stage71_energy_ml/worker.time" \
    timeout --signal=TERM 880 python -u "$stage71_scratch/ml/fit_support_augmentation.py" || stage71_status=$?
stage71_items=(workbook/stage71_energy_ml)
if [ -d "$stage71_scratch/ml/artifacts/stage71" ]; then stage71_items+=(ml/artifacts/stage71); fi
tar -czf "$stage71_scratch/results.tar.gz" -C "$stage71_scratch" "${stage71_items[@]}"
xrdcp --silent "$stage71_scratch/results.tar.gz" \
    "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage71/results.tar.gz"
exit "$stage71_status"
