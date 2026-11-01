#!/usr/bin/env bash
set -eo pipefail
mode="$1"
batch="$2"
payload="$3"
repository="$4"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_source_transfer.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
tar -xzf "$payload" -C "$scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
if [[ "$mode" == extract ]]; then
    /usr/bin/time -f 'stage48_extract wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        timeout 1200s python3 "$scratch/ml/run_source_transfer_batch.py" --batch "$batch"
    for file in "$scratch/ntuples/energy_ml_stage48/shards/"*.npz; do
        xrdcp -f --silent "$file" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage48/shards/$(basename "$file")"
    done
else
    /usr/bin/time -f 'stage48_infer wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        timeout 600s python3 "$scratch/ml/infer_source_transfer.py"
    xrdcp -f --silent "$scratch/ntuples/energy_ml_stage48/predictions.npz" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage48/predictions.npz"
fi
