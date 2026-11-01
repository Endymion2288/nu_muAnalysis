#!/usr/bin/env bash
set -eo pipefail
mode="$1"
index="$2"
payload="$3"
repository="$4"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_information.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/result"
tar -xzf "$payload" -C "$scratch/code"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
if [[ "$mode" == hits ]]; then
    (
        source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
        python3 "$scratch/code/ml/locate_calonu_native.py" --request "$scratch/code/ntuples/energy_ml_stage42/requests/request_$index.json" --output "$scratch/request.json"
    )
    export NU_MU_SKIP_LCG=1 FASER_OFFICIAL_ARCHIVE="$repository/software/calypso-master-d32b0ff3-el9-gcc13.tar.gz"
    source "$scratch/code/setup_env.sh"
    nu_mu_official_setup "$scratch/runtime"
    /usr/bin/time -f 'stage42_native wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        timeout 3300s python "$scratch/code/ml/read_calonu_sensitive_summary.py" --request "$scratch/request.json" --output "$scratch/result/$index.npz" --include "$FASER_CALYPSO_RUN/include"
    xrdcp -f --silent "$scratch/result/$index.npz" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage42/hits/$index.npz"
else
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    folds=("$index")
    if [[ "$index" == all ]]; then folds=(0 1 2); fi
    for fold in "${folds[@]}"; do
        /usr/bin/time -f 'stage42_train wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
            timeout 1800s python3 "$scratch/code/ml/run_calonu_information.py" --part "$mode" --fold "$fold"
        for file in "$scratch/code/ml/artifacts/stage42/$mode/$fold/"*; do
            xrdcp -f --silent "$file" "root://eoshome-x.cern.ch/$repository/ml/artifacts/stage42/$mode/$fold/$(basename "$file")"
        done
    done
fi
