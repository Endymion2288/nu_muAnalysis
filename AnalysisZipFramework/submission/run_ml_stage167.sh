#!/usr/bin/env bash
set -eo pipefail
stage167_phase=$1
stage167_script=${stage167_phase%_retry}
stage167_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage167.XXXXXX")
tar -xzf energy-ml-stage167.tar.gz -C "$stage167_work"
cd "$stage167_work"
mkdir -p workbook/stage167_energy_ml ntuples/energy_ml_stage167
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage167_start
stage167_status=0
(
 source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
 /usr/bin/time -v -o "workbook/stage167_energy_ml/${stage167_phase}_time.txt" python -u "ml/stage167_${stage167_script}.py" > "workbook/stage167_energy_ml/${stage167_phase}.log" 2>&1 || exit $?
) || stage167_status=$?
printf '%s\n' "$stage167_status" > "workbook/stage167_energy_ml/${stage167_phase}_exitcode.txt"
find workbook/stage167_energy_ml ntuples/energy_ml_stage167 -type f -newer .stage167_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage167/${stage167_phase}_result.tar.gz"
exit "$stage167_status"
