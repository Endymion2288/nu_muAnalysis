#!/usr/bin/env bash
set -eo pipefail
architecture="$1"
mode="$2"
payload="$3"
repository="$4"
configuration="${5:-ml/configs/prior.yaml}"
stage="${6:-21}"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_prior.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/results"
tar -xzf "$payload" -C "$scratch/code"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
for wheel in "$scratch/code/software/energy_ml_tabular_deps/"*.whl; do
    export PYTHONPATH="$wheel${PYTHONPATH:+:$PYTHONPATH}"
done
/usr/bin/time -f 'prior_train wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
    python3 -u "$scratch/code/ml/train_prior.py" --repo "$scratch/code" \
    --architecture "$architecture" --mode "$mode" --config "$configuration" --output-dir "$scratch/results"
endpoint=root://eoshome-x.cern.ch
destination="${architecture}_${mode}"
for folder in "workbook/stage${stage}_energy_ml" "ml/artifacts/stage${stage}"; do
    xrdfs "$endpoint" mkdir -p "$repository/$folder/$destination"
done
for file in "$scratch/results/"*; do
    case "$file" in
        *.pt|*.ubj|*/predictions.npz|*/preprocessing.json) folder="ml/artifacts/stage${stage}" ;;
        *) folder="workbook/stage${stage}_energy_ml" ;;
    esac
    xrdcp -f --silent "$file" "$endpoint/$repository/$folder/$destination/$(basename "$file")"
done
