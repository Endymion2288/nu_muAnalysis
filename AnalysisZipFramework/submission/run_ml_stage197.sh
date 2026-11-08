#!/usr/bin/env bash
set -eo pipefail
stage197_phase=$1
stage197_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage197.XXXXXX")
tar -xzf energy-ml-stage197.tar.gz -C "$stage197_work"
cd "$stage197_work"
mkdir -p workbook/stage197_energy_ml ntuples/energy_ml_stage197
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
touch .stage197_start
stage197_status=0
stage197_script=stage197_measure.py
if [[ "$stage197_phase" == audit ]]; then stage197_script=stage197_audit.py; fi
/usr/bin/time -v -o "workbook/stage197_energy_ml/${stage197_phase}_time.txt" python -u "ml/${stage197_script}" "$stage197_phase" > "workbook/stage197_energy_ml/${stage197_phase}.log" 2>&1 || stage197_status=$?
printf '%s\n' "$stage197_status" > "workbook/stage197_energy_ml/${stage197_phase}_exitcode.txt"
find workbook/stage197_energy_ml ntuples/energy_ml_stage197 -type f -newer .stage197_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage197/${stage197_phase}_result.tar.gz"
exit "$stage197_status"
