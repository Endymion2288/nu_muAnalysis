#!/usr/bin/env bash
set -eo pipefail
stage142_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage142.XXXXXX")
tar -xzf energy-ml-stage142.tar.gz -C "$stage142_work"
cd "$stage142_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export NU_MU_SKIP_LCG=1
source setup_env.sh
nu_mu_official_setup "$stage142_work/runtime"
mkdir -p workbook/stage142_energy_ml ntuples/energy_ml_stage142 ml/artifacts/stage142
touch .stage142_start
stage142_status=0
/usr/bin/time -v -o workbook/stage142_energy_ml/source_time.txt python -u ml/stage142_control.py || stage142_status=$?
printf '%s\n' "$stage142_status" > workbook/stage142_energy_ml/source_exitcode.txt
find workbook/stage142_energy_ml ntuples/energy_ml_stage142 ml/artifacts/stage142 -type f -newer .stage142_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage142/source_result.tar.gz
exit "$stage142_status"
