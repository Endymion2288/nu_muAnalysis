#!/usr/bin/env bash
set -eo pipefail
stage140_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage140.XXXXXX")
tar -xzf energy-ml-stage140.tar.gz -C "$stage140_work"
cd "$stage140_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p workbook/stage140_energy_ml ntuples/energy_ml_stage140 ml/artifacts/stage140
touch .stage140_start
stage140_status=0
/usr/bin/time -v -o workbook/stage140_energy_ml/pilot_time.txt python -u ml/stage140_pilot.py || stage140_status=$?
printf '%s\n' "$stage140_status" > workbook/stage140_energy_ml/pilot_exitcode.txt
find workbook/stage140_energy_ml ntuples/energy_ml_stage140 ml/artifacts/stage140 -type f -newer .stage140_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage140/pilot_result.tar.gz
exit "$stage140_status"
