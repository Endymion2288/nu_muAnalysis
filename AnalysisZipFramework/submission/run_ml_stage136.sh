#!/usr/bin/env bash
set -eo pipefail
stage136_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage136.XXXXXX")
tar -xzf energy-ml-stage136.tar.gz -C "$stage136_work"
cd "$stage136_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p workbook/stage136_energy_ml ntuples/energy_ml_stage136 ml/artifacts/stage136
touch .stage136_start
stage136_status=0
/usr/bin/time -v -o workbook/stage136_energy_ml/analysis_time.txt python -u ml/stage136_analysis.py || stage136_status=$?
printf '%s\n' "$stage136_status" > workbook/stage136_energy_ml/analysis_exitcode.txt
find workbook/stage136_energy_ml ntuples/energy_ml_stage136 ml/artifacts/stage136 -type f -newer .stage136_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage136/analysis_result.tar.gz
exit "$stage136_status"
