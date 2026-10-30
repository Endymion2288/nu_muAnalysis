#!/usr/bin/env bash
set -eo pipefail
architecture="$1"
version="$2"
payload="$3"
reports="$4"
artifacts="$5"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_tabular.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/results"
tar -xzf "$payload" -C "$scratch/code"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
export PYTHONPATH="$scratch/code/software/energy_ml_tabular_packages${PYTHONPATH:+:$PYTHONPATH}"
/usr/bin/time -f 'tabular wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
    python3 -u "$scratch/code/ml/train_tabular.py" --repo "$scratch/code" \
    --architecture "$architecture" --version "$version" --output-dir "$scratch/results"
endpoint=root://eoshome-x.cern.ch
destination="${architecture}_${version}"
xrdfs "$endpoint" mkdir -p "$reports/$destination"
xrdfs "$endpoint" mkdir -p "$artifacts/$destination"
for file in "$scratch/results/"*; do
    case "$file" in
        *.pt|*.ubj|*/predictions.npz|*/preprocessing.json) folder="$artifacts/$destination" ;;
        *) folder="$reports/$destination" ;;
    esac
    xrdcp -f --silent "$file" "$endpoint/$folder/$(basename "$file")"
done
