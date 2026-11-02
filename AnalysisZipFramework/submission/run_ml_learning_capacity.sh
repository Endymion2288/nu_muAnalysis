#!/usr/bin/env bash
set -eo pipefail
payload="$1"
repository="$2"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_learning_capacity.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
tar -xzf "$payload" -C "$scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
for fold in 0 1 2; do
    /usr/bin/time -f 'stage50_train wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        timeout 450s python3 "$scratch/ml/run_learning_capacity.py" --fold "$fold"
    for file in "$scratch/ml/artifacts/stage50/formal/$fold/"*; do
        xrdcp -f --silent "$file" "root://eoshome-x.cern.ch/$repository/ml/artifacts/stage50/formal/$fold/$(basename "$file")"
    done
done
