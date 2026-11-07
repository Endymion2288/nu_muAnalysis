#!/usr/bin/env bash
set -eo pipefail
stage139_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage139.XXXXXX")
tar -xzf energy-ml-stage139.tar.gz -C "$stage139_work"
cd "$stage139_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p workbook/stage139_energy_ml ntuples/energy_ml_stage139 ml/artifacts/stage139
touch .stage139_start
stage139_status=0
/usr/bin/time -v -o workbook/stage139_energy_ml/repair_time.txt python -u ml/stage139_repair.py || stage139_status=$?
printf '%s\n' "$stage139_status" > workbook/stage139_energy_ml/repair_exitcode.txt
find workbook/stage139_energy_ml ntuples/energy_ml_stage139 ml/artifacts/stage139 -type f -newer .stage139_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage139/repair_result.tar.gz
exit "$stage139_status"
