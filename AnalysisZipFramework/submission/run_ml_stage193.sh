#!/usr/bin/env bash
set -eo pipefail
stage193_phase=$1
stage193_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage193.XXXXXX")
tar -xzf energy-ml-stage193.tar.gz -C "$stage193_work"
cd "$stage193_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p workbook/stage193_energy_ml ntuples/energy_ml_stage193
touch .stage193_start
stage193_status=0
stage193_script=run
stage193_arg=$stage193_phase
if [[ "$stage193_phase" == audit ]]; then stage193_script=audit; stage193_arg=; fi
/usr/bin/time -v -o "workbook/stage193_energy_ml/${stage193_phase}_time.txt" python -u "ml/stage193_${stage193_script}.py" $stage193_arg > "workbook/stage193_energy_ml/${stage193_phase}.log" 2>&1 || stage193_status=$?
printf '%s\n' "$stage193_status" > "workbook/stage193_energy_ml/${stage193_phase}_exitcode.txt"
find workbook/stage193_energy_ml ntuples/energy_ml_stage193 -type f -newer .stage193_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage193/${stage193_phase}_result.tar.gz"
exit "$stage193_status"
