#!/usr/bin/env bash
set -eo pipefail
payload="$1"
repository="$2"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_true_coarse_depth.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code"
tar -xzf "$payload" -C "$scratch/code"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
for fold in 0 1 2; do
    /usr/bin/time -f 'stage46_train wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        timeout 600s python3 "$scratch/code/ml/run_true_coarse_depth.py" --fold "$fold"
    for file in "$scratch/code/ml/artifacts/stage46/formal/$fold/"*; do
        xrdcp -f --silent "$file" "root://eoshome-x.cern.ch/$repository/ml/artifacts/stage46/formal/$fold/$(basename "$file")"
    done
done
