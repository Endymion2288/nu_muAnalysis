#!/usr/bin/env bash
set -eo pipefail
payload="$1"
repository="$2"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_set_prepare.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/results"
tar -xzf "$payload" -C "$scratch/code"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONNOUSERSITE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
/usr/bin/time -f 'set_prepare wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
    python3 -u "$scratch/code/ml/prepare_sets.py" --repo "$scratch/code" --cache-root "$repository" --output-dir "$scratch/results"
endpoint=root://eoshome-x.cern.ch
for file in "$scratch/results/"*; do
    case "$file" in
        *.npy|*.npz) folder=ntuples/energy_ml_stage19 ;;
        *) folder=workbook/stage19_energy_ml ;;
    esac
    xrdcp -f --silent "$file" "$endpoint/$repository/$folder/$(basename "$file")"
done
