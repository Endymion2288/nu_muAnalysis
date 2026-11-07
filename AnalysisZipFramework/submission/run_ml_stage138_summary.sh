#!/usr/bin/env bash
set -eo pipefail
stage138_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage138.XXXXXX")
tar -xzf energy-ml-stage138.tar.gz -C "$stage138_work"
cd "$stage138_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p workbook/stage138_energy_ml ntuples/energy_ml_stage138 ml/artifacts/stage138
touch .stage138_start
stage138_status=0
/usr/bin/time -v -o workbook/stage138_energy_ml/summary_time.txt python -u ml/stage138_summarize.py || stage138_status=$?
printf '%s\n' "$stage138_status" > workbook/stage138_energy_ml/summary_exitcode.txt
find workbook/stage138_energy_ml ntuples/energy_ml_stage138 ml/artifacts/stage138 -type f -newer .stage138_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage138/summary_result.tar.gz
exit "$stage138_status"
