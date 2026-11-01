#!/usr/bin/env bash
set -eo pipefail
mode="$1"
payload="$2"
repository="$3"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_response.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/result"
tar -xzf "$payload" -C "$scratch/code"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
if [[ "$mode" == source ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
    /usr/bin/time -f 'stage40_source wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        python3 "$scratch/code/ml/run_calonu_noise_control.py" --output "$scratch/result/source_noise.npz"
    xrdcp -f --silent "$scratch/result/source_noise.npz" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage40/source_noise.npz"
    xrdcp -f --silent "$scratch/result/source_noise.json" "root://eoshome-x.cern.ch/$repository/workbook/stage40_energy_ml/source_noise.json"
    exit 0
fi
case "$mode" in
    left) indices=(2 43 49) ;;
    right) indices=(105 111 119) ;;
    *) exit 2 ;;
esac
(
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
    for index in "${indices[@]}"; do
        /usr/bin/time -f "stage40_locate_$index wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S" \
            python3 "$scratch/code/ml/locate_calonu_native.py" \
            --request "$scratch/code/workbook/stage40_energy_ml/request_$index.json" --output "$scratch/request_$index.json"
    done
)
(
    export NU_MU_SKIP_LCG=1 FASER_OFFICIAL_ARCHIVE="$repository/software/calypso-master-d32b0ff3-el9-gcc13.tar.gz"
    source "$scratch/code/setup_env.sh"
    nu_mu_official_setup "$scratch/runtime"
    for index in "${indices[@]}"; do
        /usr/bin/time -f "stage40_native_$index wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S" \
            timeout 480s python "$scratch/code/ml/read_calonu_native.py" \
            --request "$scratch/request_$index.json" --output "$scratch/result/$index.npz" \
            --include "$FASER_CALYPSO_RUN/include" --compact-signal
        xrdcp -f --silent "$scratch/result/$index.npz" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage40/shards/$index.npz"
    done
)
