#!/usr/bin/env bash
set -eo pipefail
resplit_phase=$1
resplit_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_resplit87.XXXXXX")
trap 'rm -rf "$resplit_scratch"' EXIT
tar -xzf "energy-ml-resplit-stage87-${resplit_phase}.tar.gz" -C "$resplit_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
ulimit -S -t 3400
ulimit -H -t 3450
resplit_status=0
/usr/bin/time -v -o "$resplit_scratch/workbook/stage87_energy_ml/${resplit_phase}.time" \
    timeout --signal=TERM --kill-after=10 3500 python -u "$resplit_scratch/ml/resplit_energy.py" "$resplit_phase" || resplit_status=$?
resplit_items=(workbook/stage87_energy_ml)
if [[ "$resplit_phase" == prepare ]]; then
    resplit_items+=(ntuples/energy_ml_stage87/input.npz ntuples/energy_ml_stage87/split.npz)
elif [[ -d "$resplit_scratch/ml/artifacts/stage87" ]]; then
    resplit_items+=(ml/artifacts/stage87)
fi
tar -czf "$resplit_scratch/results.tar.gz" -C "$resplit_scratch" "${resplit_items[@]}"
xrdcp --silent "$resplit_scratch/results.tar.gz" "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage87/result_${resplit_phase}.tar.gz"
exit "$resplit_status"
