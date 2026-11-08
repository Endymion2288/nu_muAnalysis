#!/usr/bin/env bash
set -eo pipefail
stage194_phase=$1
stage194_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage194.XXXXXX")
tar -xzf energy-ml-stage194.tar.gz -C "$stage194_work"
cd "$stage194_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage194_energy_ml ntuples/energy_ml_stage194
touch .stage194_start
stage194_status=0
if [[ "$stage194_phase" == audit || "$stage194_phase" == review ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    stage194_script=audit
    stage194_review_arg=
    if [[ "$stage194_phase" == review ]]; then stage194_script=review; stage194_review_arg=pilot; fi
    /usr/bin/time -v -o "workbook/stage194_energy_ml/${stage194_phase}_time.txt" python -u "ml/stage194_${stage194_script}.py" $stage194_review_arg > "workbook/stage194_energy_ml/${stage194_phase}.log" 2>&1 || stage194_status=$?
else
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage194_work/runtime"
    /usr/bin/time -v -o "workbook/stage194_energy_ml/${stage194_phase}_compile_time.txt" python ml/stage194_compile.py > "workbook/stage194_energy_ml/${stage194_phase}_compile.log" 2>&1 || stage194_status=$?
    stage194_program_phase=$stage194_phase
    if [[ "$stage194_phase" == pilot_repair* ]]; then stage194_program_phase=pilot; fi
    if [[ "$stage194_status" == 0 ]]; then
        /usr/bin/time -v -o "workbook/stage194_energy_ml/${stage194_phase}_time.txt" python -u ml/stage194_native.py "$stage194_program_phase" > "workbook/stage194_energy_ml/${stage194_phase}.log" 2>&1 || stage194_status=$?
    fi
fi
printf '%s\n' "$stage194_status" > "workbook/stage194_energy_ml/${stage194_phase}_exitcode.txt"
find workbook/stage194_energy_ml ntuples/energy_ml_stage194 -type f -newer .stage194_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage194/${stage194_phase}_result.tar.gz"
exit "$stage194_status"
