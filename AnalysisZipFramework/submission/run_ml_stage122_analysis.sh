#!/usr/bin/env bash
set -eo pipefail
stage122_phase=$1
stage122_mode=$2
stage122_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage122analysis.XXXXXX")
tar -xzf "energy-ml-stage122-${stage122_phase}.tar.gz" -C "$stage122_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
cd "$stage122_scratch"
mkdir -p ntuples/energy_ml_stage122 workbook/stage122_energy_ml
case "$stage122_mode" in
    compare) stage122_command=(python -u ml/stage122_compare.py) ;;
    qa|diagnose|full) stage122_command=(python -u ml/stage122_replica_analysis.py "$stage122_mode") ;;
    finalcheck) stage122_command=(python -u ml/stage122_finalcheck.py) ;;
    *) exit 2 ;;
esac
stage122_status=0
/usr/bin/time -v -o "workbook/stage122_energy_ml/${stage122_phase}_time.txt" timeout --signal=TERM --kill-after=10 1750 "${stage122_command[@]}" || stage122_status=$?
# Return compact evidence even if a validation assertion fails.
stage122_outputs=(workbook/stage122_energy_ml)
if [[ "$stage122_mode" == full && -f ntuples/energy_ml_stage122/replica_points.npz ]]; then
    stage122_outputs+=(ntuples/energy_ml_stage122/replica_points.npz)
elif [[ "$stage122_mode" == compare ]]; then
    for stage122_path in ntuples/energy_ml_stage122/comparison_input.npz ml/artifacts/stage122; do
        if [[ -e "$stage122_path" ]]; then stage122_outputs+=("$stage122_path"); fi
    done
fi
tar -czf result.tar.gz "${stage122_outputs[@]}"
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage122/${stage122_phase}_result.tar.gz"
exit "$stage122_status"
