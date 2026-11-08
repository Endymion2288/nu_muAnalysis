#!/usr/bin/env bash
set -eo pipefail
stage187_phase=$1
stage187_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage187.XXXXXX")
tar -xzf energy-ml-stage187.tar.gz -C "$stage187_work"
cd "$stage187_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage187_energy_ml
touch .stage187_start
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage187_status=0
stage187_program=native
if [[ "$stage187_phase" == audit ]]; then stage187_program=audit; fi
/usr/bin/time -v -o "workbook/stage187_energy_ml/${stage187_phase}_time.txt" python -u "ml/stage187_${stage187_program}.py" "$stage187_phase" > "workbook/stage187_energy_ml/${stage187_phase}.log" 2>&1 || stage187_status=$?
if [[ "$stage187_phase" == pilot && "$stage187_status" == 0 ]]; then
    python -u ml/stage187_admit.py > workbook/stage187_energy_ml/admission.log 2>&1 || stage187_status=$?
fi
printf '%s\n' "$stage187_status" > "workbook/stage187_energy_ml/${stage187_phase}_exitcode.txt"
find workbook/stage187_energy_ml -type f -newer .stage187_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage187/${stage187_phase}_result.tar.gz"
exit "$stage187_status"
