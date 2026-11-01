#!/usr/bin/env bash
set -eo pipefail
seed="$1"; payload="$2"; repository="$3"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_probability.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/results"
tar -xzf "$payload" -C "$scratch/code"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
/usr/bin/time -f 'probability wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
    python3 -u "$scratch/code/ml/run_probability_representation.py" --repo "$scratch/code" \
    --seed-index "$seed" --output-dir "$scratch/results"
endpoint=root://eoshome-x.cern.ch; destination="representation/seed_$seed"
for folder in workbook/stage30_energy_ml ml/artifacts/stage30; do
    xrdfs "$endpoint" mkdir -p "$repository/$folder/$destination"
done
for file in "$scratch/results/"*; do
    case "$file" in *.npz) folder=ml/artifacts/stage30;; *) folder=workbook/stage30_energy_ml;; esac
    xrdcp -f --silent "$file" "$endpoint/$repository/$folder/$destination/$(basename "$file")"
done
