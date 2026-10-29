#!/usr/bin/env bash
# Read the existing PHYS once per audit/extraction; retain only verified scalars.
set -eo pipefail
index="$1"
input="$2"
destination="$3"
payload="$4"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_ml.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code"
tar -xzf "$payload" -C "$scratch/code"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONNOUSERSITE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
/usr/bin/time -f 'extract wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
    python3 -u "$scratch/code/AnalysisZipFramework/scripts/export_ml_dataset.py" \
    --repo "$scratch/code" --executable "$scratch/code/build/analysis" \
    --index "$index" --input "$input" --threads 1 --output "$scratch/output.npz"
# Only upload a completely validated cache; publish by rename.
endpoint=root://eoshome-x.cern.ch
partial="${destination}.partial.$(basename "$scratch")"
xrdcp -f --silent "$scratch/output.npz" "$endpoint/$partial"
xrdfs "$endpoint" mv "$partial" "$destination"
