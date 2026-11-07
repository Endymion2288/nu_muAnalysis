#!/usr/bin/env bash
set -eo pipefail
stage137_phase=$1
stage137_index=$2
stage137_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage137.XXXXXX")
tar -xzf energy-ml-stage137.tar.gz -C "$stage137_work"
cd "$stage137_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage137_energy_ml ntuples/energy_ml_stage137 ml/artifacts/stage137
touch .stage137_start
if [[ "$stage137_phase" == production ]]; then
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage137_work/runtime"
    mkdir observer
    tar -xzf software/stage135/observer-runtime.tar.gz -C observer
    export LD_LIBRARY_PATH="$stage137_work/observer/lib:${LD_LIBRARY_PATH:-}"
    export PYTHONPATH="$stage137_work/observer/python:${PYTHONPATH:-}"
    export DATAPATH="$stage137_work/observer/lib:${DATAPATH:-}"
else
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
fi
stage137_status=0
/usr/bin/time -v -o "workbook/stage137_energy_ml/${stage137_phase}_${stage137_index}_time.txt" python -u "ml/stage137_${stage137_phase}.py" "$stage137_index" || stage137_status=$?
printf '%s\n' "$stage137_status" > "workbook/stage137_energy_ml/${stage137_phase}_${stage137_index}_exitcode.txt"
find workbook/stage137_energy_ml ntuples/energy_ml_stage137 ml/artifacts/stage137 -type f -newer .stage137_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage137/${stage137_phase}_${stage137_index}_result.tar.gz"
exit "$stage137_status"
