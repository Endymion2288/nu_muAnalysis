#!/usr/bin/env bash
set -eo pipefail
index="$1"
payload="$2"
repository="$3"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_calonu_repair.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/result"
tar -xzf "$payload" -C "$scratch/code"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
(
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
    /usr/bin/time -f 'stage38_locate wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        python3 "$scratch/code/ml/locate_calonu_native.py" \
        --request "$scratch/code/workbook/stage38_energy_ml/request_$index.json" --output "$scratch/request.json"
)
(
    export NU_MU_SKIP_LCG=1 FASER_OFFICIAL_ARCHIVE="$repository/software/calypso-master-d32b0ff3-el9-gcc13.tar.gz"
    source "$scratch/code/setup_env.sh"
    nu_mu_official_setup "$scratch/runtime"
    /usr/bin/time -f 'stage38_native wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        timeout 300s python "$scratch/code/ml/read_calonu_native.py" \
        --request "$scratch/request.json" --output "$scratch/result/$index.npz" --include "$FASER_CALYPSO_RUN/include" --compact-signal
    /usr/bin/time -f 'stage38_repair wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        timeout 300s python "$scratch/code/ml/repair_calonu_wavefit.py" --all \
        --cache "$scratch/result/$index.npz" --output "$scratch/result/replay"
)
xrdcp -f --silent "$scratch/result/$index.npz" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage38/shards/$index.npz"
xrdcp -f --silent "$scratch/result/replay/replay.tsv" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage38/shards/${index}_replay.tsv"
xrdcp -f --silent "$scratch/result/replay/summary.json" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage38/shards/${index}_summary.json"
