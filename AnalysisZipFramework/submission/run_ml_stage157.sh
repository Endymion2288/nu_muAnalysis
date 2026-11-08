#!/usr/bin/env bash
set -eo pipefail
stage157_phase=$1
stage157_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage157.XXXXXX")
tar -xzf energy-ml-stage157.tar.gz -C "$stage157_work"
cd "$stage157_work"
mkdir -p workbook/stage157_energy_ml ntuples/energy_ml_stage157
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage157_start
stage157_status=0
if [[ "$stage157_phase" == audit* || "$stage157_phase" == admission ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o "workbook/stage157_energy_ml/${stage157_phase}_time.txt" python -u ml/stage157_audit.py || stage157_status=$?
else
    export NU_MU_SKIP_LCG=1 NU_MU_NATIVE_CONTROL_STAGE=157 NU_MU_CONTROL_CONDITIONS=OFLCOND-FASER-06
    source setup_env.sh
    nu_mu_official_setup "$stage157_work/runtime"
    /usr/bin/time -v -o "workbook/stage157_energy_ml/${stage157_phase}_time.txt" python -u ml/stage157_driver.py "${stage157_phase/pilot_retry/pilot}" || stage157_status=$?
    if [[ "$stage157_phase" == batch_* && "$stage157_status" == 0 ]]; then
        /usr/bin/time -v -o "workbook/stage157_energy_ml/${stage157_phase}_compact_time.txt" python -u ml/stage157_compact.py "$stage157_phase" || stage157_status=$?
    fi
fi
printf '%s\n' "$stage157_status" > "workbook/stage157_energy_ml/${stage157_phase}_exitcode.txt"
find workbook/stage157_energy_ml ntuples/energy_ml_stage157 -type f -newer .stage157_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage157/${stage157_phase}_result.tar.gz"
exit "$stage157_status"
