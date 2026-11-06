#!/usr/bin/env bash
set -eo pipefail
stage125_report_phase=$1
stage125_report_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage125_report.XXXXXX")
trap 'rm -rf "$stage125_report_work"' EXIT
tar -xzf energy-ml-stage125-report.tar.gz -C "$stage125_report_work"
cd "$stage125_report_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export NU_MU_STAGE125_INPUT_ROOT=/eos/user/x/xcheng/FASER/nu_muAnalysis
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p workbook/stage125_energy_ml ntuples/energy_ml_stage125
stage125_report_status=0
if [[ "$stage125_report_phase" == preview ]]; then export NU_MU_STAGE125_PREVIEW=1; fi
if [[ "$stage125_report_phase" == evaluate || "$stage125_report_phase" == preview ]]; then
    /usr/bin/time -v -o workbook/stage125_energy_ml/audit_time.txt python -u ml/stage125_collect.py production || stage125_report_status=$?
    if [[ "$stage125_report_status" == 0 ]]; then
        /usr/bin/time -v -o workbook/stage125_energy_ml/evaluate_time.txt python -u ml/stage125_evaluate.py || stage125_report_status=$?
    fi
    if [[ "$stage125_report_status" == 0 ]]; then
        /usr/bin/time -v -o workbook/stage125_energy_ml/validate_time.txt python -u ml/stage125_validate.py || stage125_report_status=$?
    fi
else
    export NU_MU_STAGE125_PLOT_CPUS=4
    cp "$NU_MU_STAGE125_INPUT_ROOT/ntuples/energy_ml_stage125/evaluation.npz" ntuples/energy_ml_stage125/
    cp "$NU_MU_STAGE125_INPUT_ROOT/ntuples/energy_ml_stage125/reference.npz" ntuples/energy_ml_stage125/
    cp "$NU_MU_STAGE125_INPUT_ROOT/workbook/stage125_energy_ml/"*.tsv workbook/stage125_energy_ml/
    cp "$NU_MU_STAGE125_INPUT_ROOT/workbook/stage125_energy_ml/validation.json" workbook/stage125_energy_ml/
    /usr/bin/time -v -o workbook/stage125_energy_ml/plot_time.txt python -u ml/stage125_plot.py || stage125_report_status=$?
fi
printf '%s\n' "$stage125_report_status" > workbook/stage125_energy_ml/${stage125_report_phase}_exitcode.txt
tar -czf report_result.tar.gz workbook/stage125_energy_ml ntuples/energy_ml_stage125
xrdcp --silent --force report_result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage125/${stage125_report_phase}_result.tar.gz"
exit "$stage125_report_status"
