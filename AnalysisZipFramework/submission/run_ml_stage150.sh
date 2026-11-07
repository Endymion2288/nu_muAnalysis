#!/usr/bin/env bash
set -eo pipefail
stage150_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage150.XXXXXX")
tar -xzf energy-ml-stage150.tar.gz -C "$stage150_work"
cd "$stage150_work"
mkdir -p workbook/stage150_energy_ml
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
touch .stage150_start
stage150_status=0
/usr/bin/time -v -o workbook/stage150_energy_ml/support_time.txt python -u ml/stage150_support.py || stage150_status=$?
printf '%s\n' "$stage150_status" > workbook/stage150_energy_ml/support_exitcode.txt
find workbook/stage150_energy_ml -type f -newer .stage150_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage150/support_result.tar.gz
exit "$stage150_status"
