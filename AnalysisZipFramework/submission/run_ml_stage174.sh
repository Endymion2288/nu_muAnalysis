#!/usr/bin/env bash
set -eo pipefail
stage174_phase=$1
stage174_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage174.XXXXXX")
tar -xzf energy-ml-stage174.tar.gz -C "$stage174_work"
cd "$stage174_work"
mkdir -p workbook/stage174_energy_ml ntuples/energy_ml_stage174
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage174_start
stage174_status=0
if [[ $stage174_phase == pilot ]]; then
 (
  export NU_MU_SKIP_LCG=1
  source setup_env.sh || exit $?
  nu_mu_official_setup "$stage174_work/runtime" || exit $?
  /usr/bin/time -v -o workbook/stage174_energy_ml/mapping_time.txt python -u ml/stage174_mapping.py > workbook/stage174_energy_ml/mapping.log 2>&1
 ) || stage174_status=$?
fi
if [[ $stage174_status == 0 ]]; then
 (
  source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
  /usr/bin/time -v -o "workbook/stage174_energy_ml/${stage174_phase}_time.txt" python -u "ml/stage174_${stage174_phase}.py" > "workbook/stage174_energy_ml/${stage174_phase}.log" 2>&1
 ) || stage174_status=$?
fi
printf '%s\n' "$stage174_status" > "workbook/stage174_energy_ml/${stage174_phase}_exitcode.txt"
find workbook/stage174_energy_ml ntuples/energy_ml_stage174 -type f -newer .stage174_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage174/${stage174_phase}_result.tar.gz"
exit "$stage174_status"
