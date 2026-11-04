#!/usr/bin/env bash
set -eo pipefail
candidate_action=${1:-worker}
case "$candidate_action" in
    worker) candidate_package=energy-ml-track-candidates-stage95.tar.gz; candidate_result=result; candidate_timer=job ;;
    closeout) candidate_package=energy-ml-track-candidates-stage95-closeout.tar.gz; candidate_result=closeout_result; candidate_timer=closeout ;;
    *) exit 2 ;;
esac
candidate_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage95.XXXXXX")
trap 'rm -rf "$candidate_scratch"' EXIT
tar -xzf "$candidate_package" -C "$candidate_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
candidate_status=0
/usr/bin/time -v -o "$candidate_scratch/workbook/stage95_energy_ml/$candidate_timer.time" timeout --signal=TERM --kill-after=10 1770 bash -c '
    if [[ "$2" == closeout ]]; then
        python -u "$1/ml/closeout_track_candidates.py" report
    else
        python -u "$1/ml/track_candidate_information.py" worker --processes 8 &&
        python -u "$1/ml/report_track_candidates.py"
    fi
' bash "$candidate_scratch" "$candidate_action" || candidate_status=$?
tar -czf "$candidate_scratch/$candidate_result.tar.gz" -C "$candidate_scratch" workbook/stage95_energy_ml ntuples/energy_ml_stage95
xrdcp --force --silent "$candidate_scratch/$candidate_result.tar.gz" "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage95/$candidate_result.tar.gz"
exit "$candidate_status"
