#!/usr/bin/env bash
set -eo pipefail
action="$1"; index="$2"; payload="$3"; repository="$4"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_calonu.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/result"
tar -xzf "$payload" -C "$scratch/code"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
endpoint=root://eoshome-x.cern.ch
if [ "$action" = extract ]; then
    /usr/bin/time -f 'stage35 wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        python3 -u "$scratch/code/ml/calonu_ablation.py" extract --repo "$scratch/code" --batch "$index" --output "$scratch/result/features.npz"
    xrdcp -f --silent "$scratch/result/features.npz" "$endpoint/$repository/ntuples/energy_ml_stage35/shards/$index.npz"
else
    export OMP_NUM_THREADS=4
    /usr/bin/time -f 'stage35 wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        python3 -u "$scratch/code/ml/calonu_ablation.py" train --repo "$scratch/code" --seed-index "$index" --output "$scratch/result"
    for file in "$scratch/result/"*; do
        case "$file" in *.ubj) folder=ml/artifacts/stage35;; *) folder=workbook/stage35_energy_ml;; esac
        xrdcp -f --silent "$file" "$endpoint/$repository/$folder/seed_$index/$(basename "$file")"
    done
fi
