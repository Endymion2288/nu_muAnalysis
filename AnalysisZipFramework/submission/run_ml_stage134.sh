#!/usr/bin/env bash
set -eo pipefail
stage134_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage134.XXXXXX")
tar -xzf energy-ml-stage134.tar.gz -C "$stage134_work"
cd "$stage134_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p workbook/stage134_energy_ml ntuples/energy_ml_stage134 ml/artifacts/stage134
touch .stage134_start
stage134_status=0
/usr/bin/time -v -o workbook/stage134_energy_ml/analysis_time.txt python -u ml/stage134_analysis.py || stage134_status=$?
printf '%s\n' "$stage134_status" > workbook/stage134_energy_ml/analysis_exitcode.txt
find workbook/stage134_energy_ml ntuples/energy_ml_stage134 ml/artifacts/stage134 -type f -newer .stage134_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage134/analysis_result.tar.gz
exit "$stage134_status"
