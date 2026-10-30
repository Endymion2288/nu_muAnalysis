#!/usr/bin/env bash
set -eo pipefail
batch="$1"
payload="$2"
destination="$3"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_sets.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code"
tar -xzf "$payload" -C "$scratch/code"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONNOUSERSITE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
/usr/bin/time -f 'set_extract wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
    python3 -u "$scratch/code/ml/extract_sets.py" --repo "$scratch/code" --batch "$batch" --output "$scratch/points.npz"
endpoint=root://eoshome-x.cern.ch
partial="${destination}.partial.$(basename "$scratch")"
xrdcp -f --silent "$scratch/points.npz" "$endpoint/$partial"
xrdfs "$endpoint" mv "$partial" "$destination"
