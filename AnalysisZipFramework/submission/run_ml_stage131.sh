#!/usr/bin/env bash
set -eo pipefail
stage131_phase=$1
stage131_index=$2
stage131_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage131.XXXXXX")
tar -xzf energy-ml-stage131.tar.gz -C "$stage131_work"
cd "$stage131_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage131_energy_ml ntuples/energy_ml_stage131 ml/artifacts/stage131
touch .stage131_start
if [[ "$stage131_phase" == preflight || "$stage131_phase" == pilot || "$stage131_phase" == production ]]; then
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage131_work/runtime"
    mkdir observer
    tar -xzf software/stage131/observer-runtime.tar.gz -C observer
    export LD_LIBRARY_PATH="$stage131_work/observer/lib:${LD_LIBRARY_PATH:-}"
    export PYTHONPATH="$stage131_work/observer/python:${PYTHONPATH:-}"
    export DATAPATH="$stage131_work/observer/lib:${DATAPATH:-}"
else
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
fi
stage131_status=0
/usr/bin/time -v -o "workbook/stage131_energy_ml/${stage131_phase}_${stage131_index}_time.txt" python -u "ml/stage131_${stage131_phase}.py" "$stage131_index" || stage131_status=$?
printf '%s\n' "$stage131_status" > "workbook/stage131_energy_ml/${stage131_phase}_${stage131_index}_exitcode.txt"
if [[ "$stage131_phase" == analysis || "$stage131_phase" == audit ]]; then
    # The original parent evidence already exists in the input batch archives;
    # compact.py proves the selected arrays and JSON reports reconstruct exactly.
    find workbook/stage131_energy_ml ntuples/energy_ml_stage131 ml/artifacts/stage131 -type f -newer .stage131_start \
        ! -path 'workbook/stage131_energy_ml/parent_[0-9]*' \
        ! -path 'workbook/stage131_energy_ml/production_*' \
        ! -path 'ntuples/energy_ml_stage131/parent_*_selected.npz' -print0 | tar --null -czf result.tar.gz -T -
else
    find workbook/stage131_energy_ml ntuples/energy_ml_stage131 ml/artifacts/stage131 -type f -newer .stage131_start -print0 | tar --null -czf result.tar.gz -T -
fi
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage131/${stage131_phase}_${stage131_index}_result.tar.gz"
exit "$stage131_status"
