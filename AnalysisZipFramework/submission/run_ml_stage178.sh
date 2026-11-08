#!/usr/bin/env bash
set -eo pipefail
stage178_phase=$1
stage178_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage178.XXXXXX")
tar -xzf energy-ml-stage178.tar.gz -C "$stage178_work"
cd "$stage178_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 NU_MU_SKIP_LCG=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage178_energy_ml ntuples/energy_ml_stage178
touch .stage178_start
stage178_status=0
if [[ "$stage178_phase" == replay ]]; then
    source setup_env.sh
    nu_mu_official_setup "$stage178_work/runtime"
    mkdir observer
    tar -xzf software/stage176/observer-runtime.tar.gz -C observer
    export LD_LIBRARY_PATH="$stage178_work/observer/lib:${LD_LIBRARY_PATH:-}"
    export PYTHONPATH="$stage178_work/observer/python:${PYTHONPATH:-}"
    export DATAPATH="$stage178_work/observer/lib:${DATAPATH:-}"
else
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
fi
/usr/bin/time -v -o "workbook/stage178_energy_ml/${stage178_phase}_time.txt" python -u "ml/stage178_${stage178_phase}.py" > "workbook/stage178_energy_ml/${stage178_phase}.log" 2>&1 || stage178_status=$?
printf '%s\n' "$stage178_status" > "workbook/stage178_energy_ml/${stage178_phase}_exitcode.txt"
find workbook/stage178_energy_ml ntuples/energy_ml_stage178 -type f -newer .stage178_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage178/${stage178_phase}_result.tar.gz"
exit "$stage178_status"
