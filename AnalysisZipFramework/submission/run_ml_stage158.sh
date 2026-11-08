#!/usr/bin/env bash
set -eo pipefail
stage158_phase=$1
stage158_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage158.XXXXXX")
tar -xzf energy-ml-stage158.tar.gz -C "$stage158_work"
cd "$stage158_work"
mkdir -p workbook/stage158_energy_ml ntuples/energy_ml_stage158 ml/artifacts
touch .stage158_start
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
stage158_status=0
if [[ "$stage158_phase" == pilot || "$stage158_phase" == batch_* ]]; then
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage158_work/runtime"
    /usr/bin/time -v -o "workbook/stage158_energy_ml/${stage158_phase}_driver_time.txt" python -u ml/stage158_driver.py "$stage158_phase" || stage158_status=$?
else
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o "workbook/stage158_energy_ml/${stage158_phase}_time.txt" python -u "ml/stage158_${stage158_phase}.py" || stage158_status=$?
fi
printf '%s\n' "$stage158_status" > "workbook/stage158_energy_ml/${stage158_phase}_exitcode.txt"
stage158_outputs=(workbook/stage158_energy_ml ntuples/energy_ml_stage158)
if [[ -d ml/artifacts/stage158 ]]; then stage158_outputs+=(ml/artifacts/stage158); fi
find "${stage158_outputs[@]}" -type f -newer .stage158_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage158/${stage158_phase}_result.tar.gz"
exit "$stage158_status"
