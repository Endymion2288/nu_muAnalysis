#!/usr/bin/env bash
set -eo pipefail
case "$1" in
    left) indices=(1 44 47) ;;
    right) indices=(106 110 120) ;;
    *) IFS=',' read -r -a indices <<< "$1" ;;
esac
payload="$2"
repository="$3"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_cc_waveform.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/result"
tar -xzf "$payload" -C "$scratch/code"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
(
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
    for index in "${indices[@]}"; do
    /usr/bin/time -f "stage39_locate_$index wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S" \
        python3 "$scratch/code/ml/locate_calonu_native.py" \
        --request "$scratch/code/workbook/stage39_energy_ml/request_$index.json" --output "$scratch/request_$index.json"
    done
)
(
    export NU_MU_SKIP_LCG=1 FASER_OFFICIAL_ARCHIVE="$repository/software/calypso-master-d32b0ff3-el9-gcc13.tar.gz"
    source "$scratch/code/setup_env.sh"
    nu_mu_official_setup "$scratch/runtime"
    for index in "${indices[@]}"; do
    /usr/bin/time -f "stage39_native_$index wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S" \
        timeout 480s python "$scratch/code/ml/read_calonu_native.py" \
        --request "$scratch/request_$index.json" --output "$scratch/result/$index.npz" \
        --include "$FASER_CALYPSO_RUN/include" --compact-signal
    xrdcp -f --silent "$scratch/result/$index.npz" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage39/shards/$index.npz"
    done
)
