#!/usr/bin/env bash
set -eo pipefail
stage175_phase=$1
stage175_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage175.XXXXXX")
tar -xzf energy-ml-stage175.tar.gz -C "$stage175_work"
cd "$stage175_work"
mkdir -p workbook/stage175_energy_ml ntuples/energy_ml_stage175
export NU_MU_SKIP_LCG=1
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage175_start
stage175_status=0
if [[ $stage175_phase == pilot ]]; then
 (
  export NU_MU_SKIP_LCG=1
  source setup_env.sh || exit $?
  nu_mu_official_setup "$stage175_work/runtime" || exit $?
  /usr/bin/time -v -o workbook/stage175_energy_ml/mapping_time.txt python -u ml/stage175_mapping.py > workbook/stage175_energy_ml/mapping.log 2>&1
 ) || stage175_status=$?
fi
if [[ $stage175_status == 0 ]]; then
 (
  source setup_env.sh || exit $?
  nu_mu_official_setup "$stage175_work/runtime" || exit $?
  /usr/bin/time -v -o "workbook/stage175_energy_ml/${stage175_phase}_time.txt" python -u "ml/stage175_${stage175_phase}.py" > "workbook/stage175_energy_ml/${stage175_phase}.log" 2>&1
 ) || stage175_status=$?
fi
printf '%s\n' "$stage175_status" > "workbook/stage175_energy_ml/${stage175_phase}_exitcode.txt"
find workbook/stage175_energy_ml ntuples/energy_ml_stage175 -type f -newer .stage175_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage175/${stage175_phase}_result.tar.gz"
exit "$stage175_status"
