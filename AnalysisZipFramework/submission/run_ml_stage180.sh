#!/usr/bin/env bash
set -eo pipefail
stage180_phase=$1
stage180_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage180.XXXXXX")
tar -xzf energy-ml-stage180.tar.gz -C "$stage180_work"
cd "$stage180_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p workbook/stage180_energy_ml ntuples/energy_ml_stage180
touch .stage180_start
stage180_status=0
/usr/bin/time -v -o "workbook/stage180_energy_ml/${stage180_phase}_time.txt" python -u ml/stage180_measure.py "$stage180_phase" > "workbook/stage180_energy_ml/${stage180_phase}.log" 2>&1 || stage180_status=$?
printf '%s\n' "$stage180_status" > "workbook/stage180_energy_ml/${stage180_phase}_exitcode.txt"
find workbook/stage180_energy_ml ntuples/energy_ml_stage180 -type f -newer .stage180_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage180/${stage180_phase}_result.tar.gz"
exit "$stage180_status"
