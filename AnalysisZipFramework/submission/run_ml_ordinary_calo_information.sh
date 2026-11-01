#!/usr/bin/env bash
set -eo pipefail
mode="$1"
index="$2"
payload="$3"
repository="$4"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_ordinary_calo.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/result"
tar -xzf "$payload" -C "$scratch/code"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
if [[ "$mode" == hits ]]; then
    tar -xzf "$scratch/code/ntuples/energy_ml_stage42/requests.tar.gz" -C "$scratch" "request_$index.json"
    (
        source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
        python3 "$scratch/code/ml/locate_calonu_native.py" --request "$scratch/request_$index.json" --output "$scratch/request.json"
    )
    export NU_MU_SKIP_LCG=1 FASER_OFFICIAL_ARCHIVE="$repository/software/calypso-master-d32b0ff3-el9-gcc13.tar.gz"
    source "$scratch/code/setup_env.sh"
    nu_mu_official_setup "$scratch/runtime"
    /usr/bin/time -f 'stage47_native wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        timeout 1800s python "$scratch/code/ml/read_ordinary_calo_sensitive.py" --request "$scratch/request.json" --output "$scratch/result/$index.npz" --include "$FASER_CALYPSO_RUN/include"
    xrdcp -f --silent "$scratch/result/$index.npz" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage47/hits/$index.npz"
else
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    for fold in 0 1 2; do
        /usr/bin/time -f 'stage47_train wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
            timeout 600s python3 "$scratch/code/ml/run_ordinary_calo_information.py" --fold "$fold"
        for file in "$scratch/code/ml/artifacts/stage47/formal/$fold/"*; do
            xrdcp -f --silent "$file" "root://eoshome-x.cern.ch/$repository/ml/artifacts/stage47/formal/$fold/$(basename "$file")"
        done
    done
fi
