#!/usr/bin/env bash
set -eo pipefail
mode="$1"
payload="$2"
repository="$3"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_data_noise.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code"
tar -xzf "$payload" -C "$scratch/code"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
if [[ "$mode" == extract ]]; then
    /usr/bin/time -f 'stage43_extract wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        timeout 1800s python3 "$scratch/code/ml/calonu_data_noise.py" extract --reader "$scratch/code/ml/calonu_raw_reader"
    for file in "$scratch/code/ntuples/energy_ml_stage43/shards/"*.npz; do
        xrdcp -f --silent "$file" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage43/shards/$(basename "$file")"
    done
else
    for fold in 0 1 2; do
        /usr/bin/time -f 'stage43_train wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
            timeout 1800s python3 "$scratch/code/ml/run_calonu_data_noise.py" --fold "$fold"
        for file in "$scratch/code/ml/artifacts/stage43/formal/$fold/"*; do
            xrdcp -f --silent "$file" "root://eoshome-x.cern.ch/$repository/ml/artifacts/stage43/formal/$fold/$(basename "$file")"
        done
    done
fi
