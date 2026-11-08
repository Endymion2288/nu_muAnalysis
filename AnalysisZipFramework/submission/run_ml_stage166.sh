#!/usr/bin/env bash
set -eo pipefail
stage166_phase=$1
stage166_script=${stage166_phase%_retry}
stage166_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage166.XXXXXX")
tar -xzf energy-ml-stage166.tar.gz -C "$stage166_work"
cd "$stage166_work"
mkdir -p workbook/stage166_energy_ml ntuples/energy_ml_stage166
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage166_start
stage166_status=0
(
 source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
 /usr/bin/time -v -o "workbook/stage166_energy_ml/${stage166_phase}_time.txt" python -u "ml/stage166_${stage166_script}.py" > "workbook/stage166_energy_ml/${stage166_phase}.log" 2>&1 || exit $?
) || stage166_status=$?
printf '%s\n' "$stage166_status" > "workbook/stage166_energy_ml/${stage166_phase}_exitcode.txt"
find workbook/stage166_energy_ml ntuples/energy_ml_stage166 -type f -newer .stage166_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage166/${stage166_phase}_result.tar.gz"
exit "$stage166_status"
