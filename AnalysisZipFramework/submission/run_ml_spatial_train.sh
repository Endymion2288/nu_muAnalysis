#!/usr/bin/env bash
set -eo pipefail
seed="$1"
payload="$2"
repository="$3"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_spatial_train.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/results"
tar -xzf "$payload" -C "$scratch/code"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONNOUSERSITE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
/usr/bin/time -f 'spatial_train wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
    python3 -u "$scratch/code/ml/train_spatial.py" --repo "$scratch/code" --cache-root "$repository" \
    --seed-index "$seed" --output-dir "$scratch/results"
endpoint=root://eoshome-x.cern.ch
for folder in workbook/stage18_energy_ml ml/artifacts/stage18; do
    xrdfs "$endpoint" mkdir -p "$repository/$folder/seed_$seed"
done
for file in "$scratch/results/"*; do
    case "$file" in
        *.ubj|*/predictions.npz|*/preprocessing.json) folder=ml/artifacts/stage18 ;;
        *) folder=workbook/stage18_energy_ml ;;
    esac
    xrdcp -f --silent "$file" "$endpoint/$repository/$folder/seed_$seed/$(basename "$file")"
done
