#!/usr/bin/env bash
set -eo pipefail
stage184_phase=$1
stage184_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage184.XXXXXX")
tar -xzf energy-ml-stage184.tar.gz -C "$stage184_work"
cd "$stage184_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 NU_MU_SKIP_LCG=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage184_energy_ml ntuples/energy_ml_stage184
touch .stage184_start
source setup_env.sh
nu_mu_official_setup "$stage184_work/runtime"
stage184_status=0
/usr/bin/time -v -o "workbook/stage184_energy_ml/${stage184_phase}_time.txt" python -u ml/stage184_driver.py "$stage184_phase" > "workbook/stage184_energy_ml/${stage184_phase}.log" 2>&1 || stage184_status=$?
printf '%s\n' "$stage184_status" > "workbook/stage184_energy_ml/${stage184_phase}_exitcode.txt"
find workbook/stage184_energy_ml ntuples/energy_ml_stage184 -type f -newer .stage184_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage184/${stage184_phase}_result.tar.gz"
exit "$stage184_status"
