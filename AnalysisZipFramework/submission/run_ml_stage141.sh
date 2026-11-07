#!/usr/bin/env bash
set -eo pipefail
stage141_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage141.XXXXXX")
tar -xzf energy-ml-stage141.tar.gz -C "$stage141_work"
cd "$stage141_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p workbook/stage141_energy_ml ntuples/energy_ml_stage141 ml/artifacts/stage141
touch .stage141_start
stage141_status=0
/usr/bin/time -v -o workbook/stage141_energy_ml/control_time.txt python -u ml/stage141_control.py || stage141_status=$?
printf '%s\n' "$stage141_status" > workbook/stage141_energy_ml/control_exitcode.txt
find workbook/stage141_energy_ml ntuples/energy_ml_stage141 ml/artifacts/stage141 -type f -newer .stage141_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage141/control_result.tar.gz
exit "$stage141_status"
