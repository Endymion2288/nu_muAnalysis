#!/usr/bin/env bash
set -eo pipefail
stage160_phase=$1
stage160_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage160.XXXXXX")
tar -xzf energy-ml-stage160.tar.gz -C "$stage160_work"
cd "$stage160_work"
mkdir -p workbook/stage160_energy_ml ntuples/energy_ml_stage160
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage160_start
stage160_status=0
if [[ "$stage160_phase" == headers ]]; then
    (
        source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
        /usr/bin/time -v -o workbook/stage160_energy_ml/targets_time.txt python -u ml/stage160_targets.py
    ) || stage160_status=$?
fi
stage160_native=1
if [[ "$stage160_phase" == admission || "$stage160_phase" == headers_decision ]]; then stage160_native=0; fi
if [[ "$stage160_phase" == audit ]] && ! python3 ml/stage160_decide.py need_audit; then stage160_native=0; fi
if [[ "$stage160_status" == 0 && "$stage160_native" == 1 ]]; then
    (
        export NU_MU_SKIP_LCG=1
        source setup_env.sh || exit $?
        nu_mu_official_setup "$stage160_work/runtime" || exit $?
        /usr/bin/time -v -o "workbook/stage160_energy_ml/${stage160_phase}_time.txt" python -u ml/stage160_native.py "$stage160_phase" > "workbook/stage160_energy_ml/${stage160_phase}.log" 2>&1
    ) || stage160_status=$?
fi
if [[ "$stage160_status" == 0 && "$stage160_phase" != pilot ]]; then
    stage160_decision_phase=$stage160_phase
    if [[ "$stage160_phase" == headers_decision ]]; then stage160_decision_phase=headers; fi
    /usr/bin/time -v -o "workbook/stage160_energy_ml/${stage160_phase}_decision_time.txt" python3 ml/stage160_decide.py "$stage160_decision_phase" || stage160_status=$?
fi
printf '%s\n' "$stage160_status" > "workbook/stage160_energy_ml/${stage160_phase}_exitcode.txt"
find workbook/stage160_energy_ml ntuples/energy_ml_stage160 -type f -newer .stage160_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage160/${stage160_phase}_result.tar.gz"
exit "$stage160_status"
