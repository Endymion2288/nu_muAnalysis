#!/usr/bin/env bash
set -eo pipefail
stage190_phase=$1
stage190_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage190.XXXXXX")
tar -xzf energy-ml-stage190.tar.gz -C "$stage190_work"
cd "$stage190_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage190_energy_ml ntuples/energy_ml_stage190
touch .stage190_start
stage190_status=0
if [[ "$stage190_phase" == audit || "$stage190_phase" == review ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    stage190_script=audit
    stage190_review_arg=
    if [[ "$stage190_phase" == review ]]; then stage190_script=review; stage190_review_arg=pilot; fi
    /usr/bin/time -v -o "workbook/stage190_energy_ml/${stage190_phase}_time.txt" python -u "ml/stage190_${stage190_script}.py" $stage190_review_arg > "workbook/stage190_energy_ml/${stage190_phase}.log" 2>&1 || stage190_status=$?
else
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage190_work/runtime"
    /usr/bin/time -v -o "workbook/stage190_energy_ml/${stage190_phase}_compile_time.txt" python ml/stage190_compile.py > "workbook/stage190_energy_ml/${stage190_phase}_compile.log" 2>&1 || stage190_status=$?
    stage190_program_phase=$stage190_phase
    if [[ "$stage190_phase" == pilot_repair* ]]; then stage190_program_phase=pilot; fi
    if [[ "$stage190_status" == 0 ]]; then
        /usr/bin/time -v -o "workbook/stage190_energy_ml/${stage190_phase}_time.txt" python -u ml/stage190_native.py "$stage190_program_phase" > "workbook/stage190_energy_ml/${stage190_phase}.log" 2>&1 || stage190_status=$?
    fi
fi
printf '%s\n' "$stage190_status" > "workbook/stage190_energy_ml/${stage190_phase}_exitcode.txt"
find workbook/stage190_energy_ml ntuples/energy_ml_stage190 -type f -newer .stage190_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage190/${stage190_phase}_result.tar.gz"
exit "$stage190_status"
