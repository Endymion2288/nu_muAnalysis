#!/usr/bin/env bash
set -eo pipefail
stage168_phase=$1
stage168_script=${stage168_phase%_retry}
stage168_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage168.XXXXXX")
tar -xzf energy-ml-stage168.tar.gz -C "$stage168_work"
cd "$stage168_work"
mkdir -p workbook/stage168_energy_ml ntuples/energy_ml_stage168
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage168_start
stage168_status=0
(
 source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
 /usr/bin/time -v -o "workbook/stage168_energy_ml/${stage168_phase}_time.txt" python -u "ml/stage168_${stage168_script}.py" > "workbook/stage168_energy_ml/${stage168_phase}.log" 2>&1 || exit $?
) || stage168_status=$?
printf '%s\n' "$stage168_status" > "workbook/stage168_energy_ml/${stage168_phase}_exitcode.txt"
find workbook/stage168_energy_ml ntuples/energy_ml_stage168 -type f -newer .stage168_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage168/${stage168_phase}_result.tar.gz"
exit "$stage168_status"
