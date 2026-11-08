#!/usr/bin/env bash
set -eo pipefail
stage189_phase=$1
stage189_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage189.XXXXXX")
tar -xzf energy-ml-stage189.tar.gz -C "$stage189_work"
cd "$stage189_work"
mkdir -p workbook/stage189_energy_ml ml/artifacts/stage189 ntuples/energy_ml_stage189
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage189_start
stage189_status=0
stage189_program_phase=$stage189_phase
if [[ "$stage189_phase" == audit_repair ]]; then stage189_program_phase=audit; fi
if [[ $stage189_status == 0 ]]; then
 (
  source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
  /usr/bin/time -v -o "workbook/stage189_energy_ml/${stage189_phase}_time.txt" python -u "ml/stage189_${stage189_program_phase}.py" > "workbook/stage189_energy_ml/${stage189_phase}.log" 2>&1
 ) || stage189_status=$?
fi
printf '%s\n' "$stage189_status" > "workbook/stage189_energy_ml/${stage189_phase}_exitcode.txt"
find workbook/stage189_energy_ml ml/artifacts/stage189 ntuples/energy_ml_stage189 -type f -newer .stage189_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage189/${stage189_phase}_result.tar.gz"
exit "$stage189_status"
