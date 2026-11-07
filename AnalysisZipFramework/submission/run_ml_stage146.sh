#!/usr/bin/env bash
set -eo pipefail
stage146_phase=$1
stage146_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage146.XXXXXX")
tar -xzf energy-ml-stage146.tar.gz -C "$stage146_work"
cd "$stage146_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage146_start
stage146_status=0
if [[ "$stage146_phase" == score ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o workbook/stage146_energy_ml/score_time.txt python -u ml/stage146_score.py || stage146_status=$?
else
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage146_work/runtime"
    /usr/bin/time -v -o "workbook/stage146_energy_ml/${stage146_phase}_time.txt" python -u ml/stage146_native.py "$stage146_phase" || stage146_status=$?
fi
printf '%s\n' "$stage146_status" > "workbook/stage146_energy_ml/${stage146_phase}_exitcode.txt"
find workbook/stage146_energy_ml -type f -newer .stage146_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage146/${stage146_phase}_result.tar.gz"
exit "$stage146_status"
