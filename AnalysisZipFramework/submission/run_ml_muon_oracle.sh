#!/usr/bin/env bash
set -eo pipefail
seed_index="$1"
payload="$2"
reports="$3"
artifacts="$4"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_oracle.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/results"
tar -xzf "$payload" -C "$scratch/code"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONNOUSERSITE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
/usr/bin/time -f 'muon_oracle wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
    python3 -u "$scratch/code/ml/muon_oracle.py" --repo "$scratch/code" \
    --seed-index "$seed_index" --output-dir "$scratch/results"
endpoint=root://eoshome-x.cern.ch
xrdfs "$endpoint" mkdir -p "$reports/seed_$seed_index"
xrdfs "$endpoint" mkdir -p "$artifacts/seed_$seed_index"
for file in "$scratch/results/"*; do
    case "$file" in
        *.ubj|*.features.json|*/predictions.npz) destination="$artifacts/seed_$seed_index" ;;
        *) destination="$reports/seed_$seed_index" ;;
    esac
    # Only seed0 checkpoints are needed for later inspection.
    case "$file" in
        *.ubj|*.features.json) if [ "$seed_index" != 0 ]; then continue; fi ;;
    esac
    xrdcp -f --silent "$file" "$endpoint/$destination/$(basename "$file")"
done
