#!/usr/bin/env bash
set -eo pipefail
batch="$1"
payload="$2"
repository="$3"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_f6_response.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
tar -xzf "$payload" -C "$scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
for offset in 0 6 12; do
    index=$((batch+offset))
    /usr/bin/time -f 'stage52_extract wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        timeout 600s python3 "$scratch/ml/read_f6_muon_response.py" --index "$index" --output "$scratch/$index.npz"
    xrdcp -f --silent "$scratch/$index.npz" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage52/shards/$index.npz"
    rm "$scratch/$index.npz"
done
