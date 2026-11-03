#!/usr/bin/env bash
set -eo pipefail
stage81_index="$1"
case "$stage81_index" in 0|1) ;; *) exit 2;; esac
stage81_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_phys_support.XXXXXX")
trap 'rm -rf "$stage81_scratch"' EXIT
tar -xzf energy-ml-phys-support-stage81.tar.gz -C "$stage81_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage81_status=0
/usr/bin/time -f 'wall_s=%e user_s=%U system_s=%S maxRSS_KiB=%M' -o "$stage81_scratch/workbook/stage81_energy_ml/worker${stage81_index}.time" \
    timeout --signal=TERM --kill-after=10 3500 python -u "$stage81_scratch/ml/extract_phys_support.py" --index "$stage81_index" \
    > "$stage81_scratch/workbook/stage81_energy_ml/worker${stage81_index}.txt" 2>&1 || stage81_status=$?
stage81_items=("workbook/stage81_energy_ml/worker${stage81_index}.time" "workbook/stage81_energy_ml/worker${stage81_index}.txt")
if [ -f "$stage81_scratch/ntuples/energy_ml_stage81/source${stage81_index}.npz" ]; then
    stage81_items+=("ntuples/energy_ml_stage81/source${stage81_index}.npz")
fi
tar -czf "$stage81_scratch/results.tar.gz" -C "$stage81_scratch" "${stage81_items[@]}"
xrdcp --silent "$stage81_scratch/results.tar.gz" \
    "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage81/source_${stage81_index}.tar.gz"
exit "$stage81_status"
