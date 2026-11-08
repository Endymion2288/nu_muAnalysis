#!/usr/bin/env bash
set -eo pipefail
stage191_phase=$1
stage191_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage191.XXXXXX")
tar -xzf energy-ml-stage191.tar.gz -C "$stage191_work"
cd "$stage191_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage191_energy_ml ntuples/energy_ml_stage191 ml/artifacts/stage191
touch .stage191_start
stage191_status=0
if [[ "$stage191_phase" == review || "$stage191_phase" == review_repair || "$stage191_phase" == fit || "$stage191_phase" == audit ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    stage191_program=$stage191_phase
    if [[ "$stage191_phase" == review_repair ]]; then stage191_program=review; fi
    /usr/bin/time -v -o "workbook/stage191_energy_ml/${stage191_phase}_time.txt" python -u "ml/stage191_${stage191_program}.py" > "workbook/stage191_energy_ml/${stage191_phase}.log" 2>&1 || stage191_status=$?
else
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage191_work/runtime"
    /usr/bin/time -v -o "workbook/stage191_energy_ml/${stage191_phase}_compile_time.txt" python ml/stage191_compile.py > "workbook/stage191_energy_ml/${stage191_phase}_compile.log" 2>&1 || stage191_status=$?
    if [[ "$stage191_status" == 0 ]]; then
        if [[ "$stage191_phase" == pilot ]]; then
            /usr/bin/time -v -o workbook/stage191_energy_ml/pilot_time.txt python -u ml/stage191_native.py pilot 0 > workbook/stage191_energy_ml/pilot.log 2>&1 || stage191_status=$?
        else
            /usr/bin/time -v -o "workbook/stage191_energy_ml/${stage191_phase}_time.txt" python -u ml/stage191_driver.py "$stage191_phase" > "workbook/stage191_energy_ml/${stage191_phase}.log" 2>&1 || stage191_status=$?
        fi
    fi
fi
printf '%s\n' "$stage191_status" > "workbook/stage191_energy_ml/${stage191_phase}_exitcode.txt"
find workbook/stage191_energy_ml ntuples/energy_ml_stage191 ml/artifacts/stage191 -type f -newer .stage191_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage191/${stage191_phase}_result.tar.gz"
exit "$stage191_status"
