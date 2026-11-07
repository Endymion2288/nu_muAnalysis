#!/usr/bin/env bash
set -eo pipefail
stage144_phase=$1
stage144_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage144.XXXXXX")
tar -xzf energy-ml-stage144.tar.gz -C "$stage144_work"
cd "$stage144_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 NU_MU_SKIP_LCG=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage144_energy_ml ntuples/energy_ml_stage144
touch .stage144_start
stage144_status=0
if [[ "$stage144_phase" == audit ]]; then
    /usr/bin/time -v -o workbook/stage144_energy_ml/audit_time.txt /usr/bin/python3 -u ml/stage144_summarize.py || stage144_status=$?
else
source setup_env.sh
nu_mu_official_setup "$stage144_work/runtime"
/usr/bin/time -v -o "workbook/stage144_energy_ml/${stage144_phase}_time.txt" python -u ml/stage144_driver.py "$stage144_phase" || stage144_status=$?
fi
printf '%s\n' "$stage144_status" > "workbook/stage144_energy_ml/${stage144_phase}_exitcode.txt"
find workbook/stage144_energy_ml ntuples/energy_ml_stage144 -type f -newer .stage144_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage144/${stage144_phase}_result.tar.gz"
exit "$stage144_status"
