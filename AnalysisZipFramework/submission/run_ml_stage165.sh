#!/usr/bin/env bash
set -eo pipefail
stage165_phase=$1
stage165_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage165.XXXXXX")
tar -xzf energy-ml-stage165.tar.gz -C "$stage165_work"
cd "$stage165_work"
mkdir -p workbook/stage165_energy_ml ntuples/energy_ml_stage165
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage165_start
stage165_status=0
(
 source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
 /usr/bin/time -v -o "workbook/stage165_energy_ml/${stage165_phase}_time.txt" python -u "ml/stage165_${stage165_phase}.py" > "workbook/stage165_energy_ml/${stage165_phase}.log" 2>&1 || exit $?
 if [[ "$stage165_phase" == analysis ]]; then python -u ml/stage165_plot.py; fi
) || stage165_status=$?
printf '%s\n' "$stage165_status" > "workbook/stage165_energy_ml/${stage165_phase}_exitcode.txt"
find workbook/stage165_energy_ml -type f -newer .stage165_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage165/${stage165_phase}_result.tar.gz"
exit "$stage165_status"
