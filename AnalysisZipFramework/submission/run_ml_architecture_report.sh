#!/usr/bin/env bash
set -eo pipefail
architecture_report_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage94_report.XXXXXX")
trap 'rm -rf "$architecture_report_scratch"' EXIT
tar -xzf energy-ml-architecture-report-stage94.tar.gz -C "$architecture_report_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
architecture_report_status=0
/usr/bin/time -v -o "$architecture_report_scratch/workbook/stage94_energy_ml/report_job.time" timeout --signal=TERM --kill-after=10 1770 bash -c '
    python -u "$1/ml/report_energy_architectures.py" --processes 4 &&
    python -u "$1/ml/validate_energy_architectures.py" &&
    python -u "$1/ml/closeout_energy_architectures.py"
' bash "$architecture_report_scratch" || architecture_report_status=$?
tar -czf "$architecture_report_scratch/result_report.tar.gz" -C "$architecture_report_scratch" workbook/stage94_energy_ml
xrdcp --force --silent "$architecture_report_scratch/result_report.tar.gz" root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage94/result_report.tar.gz
exit "$architecture_report_status"
