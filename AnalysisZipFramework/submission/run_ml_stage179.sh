#!/usr/bin/env bash
set -eo pipefail
stage179_phase=$1
stage179_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage179.XXXXXX")
tar -xzf energy-ml-stage179.tar.gz -C "$stage179_work"
cd "$stage179_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 NU_MU_SKIP_LCG=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage179_energy_ml ntuples/energy_ml_stage179
touch .stage179_start
stage179_status=0
if [[ "$stage179_phase" == audit ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o workbook/stage179_energy_ml/audit_time.txt python -u ml/stage179_audit.py > workbook/stage179_energy_ml/audit.log 2>&1 || stage179_status=$?
else
    source setup_env.sh
    nu_mu_official_setup "$stage179_work/runtime"
    /usr/bin/time -v -o "workbook/stage179_energy_ml/${stage179_phase}_time.txt" python -u ml/stage179_driver.py "$stage179_phase" > "workbook/stage179_energy_ml/${stage179_phase}.log" 2>&1 || stage179_status=$?
fi
printf '%s\n' "$stage179_status" > "workbook/stage179_energy_ml/${stage179_phase}_exitcode.txt"
find workbook/stage179_energy_ml ntuples/energy_ml_stage179 -type f -newer .stage179_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage179/${stage179_phase}_result.tar.gz"
exit "$stage179_status"
