#!/usr/bin/env bash
set -eo pipefail
stage188_phase=$1
stage188_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage188.XXXXXX")
tar -xzf energy-ml-stage188.tar.gz -C "$stage188_work"
cd "$stage188_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage188_energy_ml ntuples/energy_ml_stage188
touch .stage188_start
stage188_status=0
if [[ "$stage188_phase" == audit || "$stage188_phase" == review ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    stage188_script=audit
    stage188_review_arg=
    if [[ "$stage188_phase" == review ]]; then stage188_script=review; stage188_review_arg=pilot; fi
    /usr/bin/time -v -o "workbook/stage188_energy_ml/${stage188_phase}_time.txt" python -u "ml/stage188_${stage188_script}.py" $stage188_review_arg > "workbook/stage188_energy_ml/${stage188_phase}.log" 2>&1 || stage188_status=$?
else
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage188_work/runtime"
    /usr/bin/time -v -o "workbook/stage188_energy_ml/${stage188_phase}_compile_time.txt" python ml/stage188_compile.py > "workbook/stage188_energy_ml/${stage188_phase}_compile.log" 2>&1 || stage188_status=$?
    stage188_program_phase=$stage188_phase
    if [[ "$stage188_phase" == pilot_repair* ]]; then stage188_program_phase=pilot; fi
    if [[ "$stage188_status" == 0 ]]; then
        /usr/bin/time -v -o "workbook/stage188_energy_ml/${stage188_phase}_time.txt" python -u ml/stage188_native.py "$stage188_program_phase" > "workbook/stage188_energy_ml/${stage188_phase}.log" 2>&1 || stage188_status=$?
    fi
fi
printf '%s\n' "$stage188_status" > "workbook/stage188_energy_ml/${stage188_phase}_exitcode.txt"
find workbook/stage188_energy_ml ntuples/energy_ml_stage188 -type f -newer .stage188_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage188/${stage188_phase}_result.tar.gz"
exit "$stage188_status"
