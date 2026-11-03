#!/usr/bin/env bash
# Stage83: five complete known compatible pi PHYS sources per worker.
set -eo pipefail
pi_shard=$1
pi_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_pi83.XXXXXX")
trap 'rm -rf "$pi_scratch"' EXIT
tar -xzf energy-ml-pi-support-stage83.tar.gz -C "$pi_scratch"
mkdir -p "$pi_scratch/result"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
ulimit -S -t 400
ulimit -H -t 430
pi_status=0
pi_run() {
    for pi_index in $(seq "$((pi_shard*5))" "$((pi_shard*5+4))"); do
        /usr/bin/time -f 'wall_s=%e user_s=%U system_s=%S maxRSS_KiB=%M' -o "$pi_scratch/result/source$pi_index.time" \
            timeout --signal=TERM --kill-after=10 210 python -u "$pi_scratch/ml/pi_support_delivery.py" extract --index "$pi_index" \
            > "$pi_scratch/result/source$pi_index.txt" 2>&1 || return
    done
}
pi_run || pi_status=$?
printf '%s\n' "$pi_status" > "$pi_scratch/result/exitcode.txt"
pi_items=(result)
if [[ -d "$pi_scratch/ntuples/energy_ml_stage83" ]]; then pi_items+=(ntuples/energy_ml_stage83); fi
tar -czf "$pi_scratch/results.tar.gz" -C "$pi_scratch" "${pi_items[@]}"
xrdcp --silent "$pi_scratch/results.tar.gz" "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage83/shard_$pi_shard.tar.gz"
exit "$pi_status"
