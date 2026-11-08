#!/usr/bin/env bash
set -eo pipefail
stage182_phase=$1
stage182_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage182.XXXXXX")
tar -xzf energy-ml-stage182.tar.gz -C "$stage182_work"
cd "$stage182_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p workbook/stage182_energy_ml ntuples/energy_ml_stage182
touch .stage182_start
stage182_status=0
/usr/bin/time -v -o "workbook/stage182_energy_ml/${stage182_phase}_time.txt" python -u ml/stage182_measure.py "$stage182_phase" > "workbook/stage182_energy_ml/${stage182_phase}.log" 2>&1 || stage182_status=$?
printf '%s\n' "$stage182_status" > "workbook/stage182_energy_ml/${stage182_phase}_exitcode.txt"
find workbook/stage182_energy_ml ntuples/energy_ml_stage182 -type f -newer .stage182_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage182/${stage182_phase}_result.tar.gz"
exit "$stage182_status"
