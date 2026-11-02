#!/usr/bin/env bash
set -eo pipefail
mode="$1"
batch="$2"
payload="$3"
repository="$4"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_segment_information.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
tar -xzf "$payload" -C "$scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
if [[ "$mode" == extract ]]; then
    /usr/bin/time -f 'stage51_extract wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        timeout 600s python3 "$scratch/ml/read_segment_information.py" --batch "$batch"
    for file in "$scratch/ntuples/energy_ml_stage51/shards/"*.npz; do
        xrdcp -f --silent "$file" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage51/shards/$(basename "$file")"
    done
else
    for fold in 0 1 2; do
        /usr/bin/time -f 'stage51_train wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
            timeout 450s python3 "$scratch/ml/run_segment_information.py" --fold "$fold"
        for file in "$scratch/ml/artifacts/stage51/formal/$fold/"*; do
            xrdcp -f --silent "$file" "root://eoshome-x.cern.ch/$repository/ml/artifacts/stage51/formal/$fold/$(basename "$file")"
        done
    done
fi
