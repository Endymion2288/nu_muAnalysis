#!/usr/bin/env bash
set -eo pipefail
action="$1"; index="$2"; payload="$3"; repository="$4"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_track_response.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/results"
tar -xzf "$payload" -C "$scratch/code"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
endpoint=root://eoshome-x.cern.ch
if [ "$action" = train ]; then
    /usr/bin/time -f 'stage31 wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        python3 -u "$scratch/code/ml/train_track_response.py" --repo "$scratch/code" --seed-index "$index" --output-dir "$scratch/results"
    for folder in workbook/stage31_energy_ml ml/artifacts/stage31; do
        xrdfs "$endpoint" mkdir -p "$repository/$folder/seed_$index"
    done
    for file in "$scratch/results/"*; do
        case "$file" in *.ubj|*.npz) folder=ml/artifacts/stage31;; *) folder=workbook/stage31_energy_ml;; esac
        xrdcp -f --silent "$file" "$endpoint/$repository/$folder/seed_$index/$(basename "$file")"
    done
else
    export OMP_NUM_THREADS=1
    flags=(--batch "$index")
    destination="$repository/ntuples/energy_ml_stage31/shards/$index.npz"
    if [ "$action" = data ] || [ "$action" = tracker_data ]; then
        flags=(--data)
        if [ "$action" = tracker_data ]; then flags+=(--tracker-control); fi
        destination="$repository/ntuples/energy_ml_stage31/${action}_control.npz"
    fi
    /usr/bin/time -f 'stage31 wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        python3 -u "$scratch/code/ml/extract_track_response.py" --repo "$scratch/code" "${flags[@]}" --output "$scratch/results/features.npz"
    xrdcp -f --silent "$scratch/results/features.npz" "$endpoint/$destination"
fi
