#!/usr/bin/env bash
set -eo pipefail
part="$1"; batch="$2"; payload="$3"; repository="$4"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_frozen.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code"
tar -xzf "$payload" -C "$scratch/code"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
/usr/bin/time -f 'stage34 wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
    python3 -u "$scratch/code/ml/frozen_evaluation.py" extract --repo "$scratch/code" --partition "$part" \
    --batch "$batch" --output "$scratch/features.npz"
xrdcp -f --silent "$scratch/features.npz" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage34/shards/${part}_${batch}.npz"
