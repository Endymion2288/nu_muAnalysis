#!/usr/bin/env bash
set -eo pipefail
index="$1"
payload="$2"
repository="$3"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_calonu_muon.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/result"
tar -xzf "$payload" -C "$scratch/code"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
/usr/bin/time -f 'stage36 wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
    python3 -u "$scratch/code/ml/calonu_muon_control.py" extract --repo "$scratch/code" --index "$index" --output "$scratch/result/$index.npz"
xrdcp -f --silent "$scratch/result/$index.npz" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage36/shards/$index.npz"
