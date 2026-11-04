#!/usr/bin/env bash
set -eo pipefail
accurate_role=$1
accurate_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_accurate89.XXXXXX")
trap 'rm -rf "$accurate_scratch"' EXIT
tar -xzf "energy-ml-accurate-stage89-${accurate_role}.tar.gz" -C "$accurate_scratch"
mkdir -p "$accurate_scratch/workbook/stage89_energy_ml/$accurate_role"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
ulimit -S -t 5200
ulimit -H -t 5300
accurate_status=0
/usr/bin/time -v -o "$accurate_scratch/workbook/stage89_energy_ml/$accurate_role/job.time" \
    timeout --signal=TERM --kill-after=10 5340 python -u "$accurate_scratch/ml/accurate_posterior.py" worker --role "$accurate_role" || accurate_status=$?
accurate_items=("workbook/stage89_energy_ml/$accurate_role")
if [[ -f "$accurate_scratch/ntuples/energy_ml_stage89/predictions_${accurate_role}.npz" ]]; then
    accurate_items+=("ntuples/energy_ml_stage89/predictions_${accurate_role}.npz")
fi
tar -czf "$accurate_scratch/result.tar.gz" -C "$accurate_scratch" "${accurate_items[@]}"
xrdcp --silent "$accurate_scratch/result.tar.gz" "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage89/result_${accurate_role}.tar.gz"
exit "$accurate_status"
