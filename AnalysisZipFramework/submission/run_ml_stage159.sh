#!/usr/bin/env bash
set -eo pipefail
stage159_phase=$1
stage159_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage159.XXXXXX")
tar -xzf energy-ml-stage159.tar.gz -C "$stage159_work"
cd "$stage159_work"
mkdir -p workbook/stage159_energy_ml ntuples/energy_ml_stage159
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
stage159_status=0
if [[ "$stage159_phase" == identity_diagnostic ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o workbook/stage159_energy_ml/identity_diagnostic_time.txt python -u ml/stage159_identity_diagnostic.py || stage159_status=$?
else
(
    export NU_MU_SKIP_LCG=1
    source setup_env.sh || exit $?
    nu_mu_official_setup "$stage159_work/runtime" || exit $?
    /usr/bin/time -v -o workbook/stage159_energy_ml/native_64_time.txt python -u ml/stage159_native.py 64 > workbook/stage159_energy_ml/native_64.log 2>&1 || exit $?
    /usr/bin/time -v -o workbook/stage159_energy_ml/native_4_time.txt python -u ml/stage159_native.py 4 > workbook/stage159_energy_ml/native_4.log 2>&1 || exit $?
) || stage159_status=$?
if [[ "$stage159_status" == 0 ]]; then
    (
        source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
        /usr/bin/time -v -o workbook/stage159_energy_ml/pair_time.txt python -u ml/stage159_pair.py
    ) || stage159_status=$?
fi
fi
printf '%s\n' "$stage159_status" > "workbook/stage159_energy_ml/${stage159_phase}_exitcode.txt"
tar -czf result.tar.gz workbook/stage159_energy_ml ntuples/energy_ml_stage159
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage159/${stage159_phase}_result.tar.gz"
exit "$stage159_status"
