#!/usr/bin/env bash
set -eo pipefail
stage148_phase=$1
stage148_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage148.XXXXXX")
tar -xzf energy-ml-stage148.tar.gz -C "$stage148_work"
cd "$stage148_work"
mkdir -p workbook/stage148_energy_ml ntuples/energy_ml_stage148
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage148_start
stage148_status=0
if [[ "$stage148_phase" == support ]]; then
    stage148_script=ml/stage148_support.py
    /usr/bin/time -v -o "workbook/stage148_energy_ml/${stage148_phase}_time.txt" /usr/bin/python3 -u "$stage148_script" || stage148_status=$?
else
    export NU_MU_SKIP_LCG=1 NU_MU_RESPONSE_STAGE=148 NU_MU_ECAL_STAGE=148
    source setup_env.sh
    nu_mu_official_setup "$stage148_work/runtime"
    if [[ "$stage148_phase" == transport ]]; then
        mkdir observer
        tar -xzf software/stage142/observer-runtime.tar.gz -C observer
        export LD_LIBRARY_PATH="$stage148_work/observer/lib:${LD_LIBRARY_PATH:-}"
        export PYTHONPATH="$stage148_work/observer/python:${PYTHONPATH:-}"
        export DATAPATH="$stage148_work/observer/lib:${DATAPATH:-}"
        /usr/bin/time -v -o workbook/stage148_energy_ml/transport_time.txt python -u ml/stage148_transport.py || stage148_status=$?
    elif [[ "$stage148_phase" == ecal ]]; then
        stage148_index=$(python -c 'import json;print(json.load(open("workbook/stage148_energy_ml/support.json"))["selected_indices"][0])')
        /usr/bin/time -v -o workbook/stage148_energy_ml/ecal_time.txt python -u ml/stage144_native.py "$stage148_index" || stage148_status=$?
    else
        /usr/bin/time -v -o workbook/stage148_energy_ml/audit_time.txt python -u ml/stage148_summarize.py || stage148_status=$?
    fi
fi
printf '%s\n' "$stage148_status" > "workbook/stage148_energy_ml/${stage148_phase}_exitcode.txt"
find workbook/stage148_energy_ml ntuples/energy_ml_stage148 -type f -newer .stage148_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage148/${stage148_phase}_result.tar.gz"
exit "$stage148_status"
