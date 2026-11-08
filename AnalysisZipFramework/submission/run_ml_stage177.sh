#!/usr/bin/env bash
set -eo pipefail
stage177_phase=$1
stage177_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage177.XXXXXX")
tar -xzf energy-ml-stage177.tar.gz -C "$stage177_work"
cd "$stage177_work"
mkdir -p workbook/stage177_energy_ml ml/artifacts/stage177
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage177_start
stage177_status=0
if [[ $stage177_status == 0 ]]; then
 (
  source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
  /usr/bin/time -v -o "workbook/stage177_energy_ml/${stage177_phase}_time.txt" python -u "ml/stage177_${stage177_phase}.py" > "workbook/stage177_energy_ml/${stage177_phase}.log" 2>&1
 ) || stage177_status=$?
fi
printf '%s\n' "$stage177_status" > "workbook/stage177_energy_ml/${stage177_phase}_exitcode.txt"
find workbook/stage177_energy_ml ml/artifacts/stage177 -type f -newer .stage177_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage177/${stage177_phase}_result.tar.gz"
exit "$stage177_status"
