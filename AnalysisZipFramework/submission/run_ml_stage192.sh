#!/usr/bin/env bash
set -eo pipefail
stage192_phase=$1
stage192_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage192.XXXXXX")
tar -xzf energy-ml-stage192.tar.gz -C "$stage192_work"
cd "$stage192_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage192_energy_ml ntuples/energy_ml_stage192
touch .stage192_start
stage192_status=0
if [[ "$stage192_phase" == audit || "$stage192_phase" == review ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    stage192_script=audit
    stage192_review_arg=
    if [[ "$stage192_phase" == review ]]; then stage192_script=review; stage192_review_arg=pilot; fi
    /usr/bin/time -v -o "workbook/stage192_energy_ml/${stage192_phase}_time.txt" python -u "ml/stage192_${stage192_script}.py" $stage192_review_arg > "workbook/stage192_energy_ml/${stage192_phase}.log" 2>&1 || stage192_status=$?
else
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage192_work/runtime"
    /usr/bin/time -v -o "workbook/stage192_energy_ml/${stage192_phase}_compile_time.txt" python ml/stage192_compile.py > "workbook/stage192_energy_ml/${stage192_phase}_compile.log" 2>&1 || stage192_status=$?
    stage192_program_phase=$stage192_phase
    if [[ "$stage192_phase" == pilot_repair* ]]; then stage192_program_phase=pilot; fi
    if [[ "$stage192_status" == 0 ]]; then
        /usr/bin/time -v -o "workbook/stage192_energy_ml/${stage192_phase}_time.txt" python -u ml/stage192_native.py "$stage192_program_phase" > "workbook/stage192_energy_ml/${stage192_phase}.log" 2>&1 || stage192_status=$?
    fi
fi
printf '%s\n' "$stage192_status" > "workbook/stage192_energy_ml/${stage192_phase}_exitcode.txt"
find workbook/stage192_energy_ml ntuples/energy_ml_stage192 -type f -newer .stage192_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage192/${stage192_phase}_result.tar.gz"
exit "$stage192_status"
