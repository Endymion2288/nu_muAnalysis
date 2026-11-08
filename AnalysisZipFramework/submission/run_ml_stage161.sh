#!/usr/bin/env bash
set -eo pipefail
stage161_attempt=$1
stage161_phase=$stage161_attempt
if [[ "$stage161_attempt" == pilot_* ]]; then stage161_phase=pilot; fi
stage161_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage161.XXXXXX")
tar -xzf energy-ml-stage161.tar.gz -C "$stage161_work"
cd "$stage161_work"
mkdir -p workbook/stage161_energy_ml ntuples/energy_ml_stage161
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage161_start
stage161_status=0
if [[ "$stage161_attempt" == identity_diagnostic ]]; then
    /usr/bin/time -v -o workbook/stage161_energy_ml/identity_diagnostic_time.txt python3 -u ml/stage161_diagnostic.py || stage161_status=$?
else
(
    export NU_MU_SKIP_LCG=1
    source setup_env.sh || exit $?
    nu_mu_official_setup "$stage161_work/runtime" || exit $?
    if [[ "$stage161_attempt" != pilot_conditions ]]; then
        /usr/bin/time -v -o "workbook/stage161_energy_ml/${stage161_phase}_raw_time.txt" python -u ml/stage161_raw.py "$stage161_phase" > "workbook/stage161_energy_ml/${stage161_phase}_raw.log" 2>&1 || exit $?
    fi
    /usr/bin/time -v -o "workbook/stage161_energy_ml/${stage161_phase}_conditions_time.txt" python -u ml/stage161_conditions.py || exit $?
    /usr/bin/time -v -o "workbook/stage161_energy_ml/${stage161_phase}_native_time.txt" python -u ml/stage161_native.py "$stage161_phase" > "workbook/stage161_energy_ml/${stage161_phase}_native.log" 2>&1
) || stage161_status=$?
if [[ "$stage161_status" == 0 ]]; then
    (
        source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
        /usr/bin/time -v -o "workbook/stage161_energy_ml/${stage161_phase}_comparison_time.txt" python -u ml/stage161_compare.py "$stage161_phase"
    ) || stage161_status=$?
fi
fi
printf '%s\n' "$stage161_status" > "workbook/stage161_energy_ml/${stage161_phase}_exitcode.txt"
find workbook/stage161_energy_ml ntuples/energy_ml_stage161 -type f -newer .stage161_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage161/${stage161_attempt}_result.tar.gz"
exit "$stage161_status"
