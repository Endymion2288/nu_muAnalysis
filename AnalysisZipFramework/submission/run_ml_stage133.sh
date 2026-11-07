#!/usr/bin/env bash
set -eo pipefail
stage133_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage133.XXXXXX")
tar -xzf energy-ml-stage133.tar.gz -C "$stage133_work"
cd "$stage133_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p workbook/stage133_energy_ml ntuples/energy_ml_stage133 ml/artifacts/stage133
touch .stage133_start
stage133_status=0
/usr/bin/time -v -o workbook/stage133_energy_ml/analysis_time.txt python -u ml/stage133_analysis.py || stage133_status=$?
printf '%s\n' "$stage133_status" > workbook/stage133_energy_ml/analysis_exitcode.txt
find workbook/stage133_energy_ml ntuples/energy_ml_stage133 ml/artifacts/stage133 -type f -newer .stage133_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage133/analysis_result.tar.gz
exit "$stage133_status"
