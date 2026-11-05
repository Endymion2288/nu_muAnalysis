#!/usr/bin/env bash
set -eo pipefail
stage110_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage110.XXXXXX")
trap 'rm -rf "$stage110_scratch"' EXIT
tar -xzf energy-ml-stage110.tar.gz -C "$stage110_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
cd "$stage110_scratch"
mkdir -p workbook/stage110_energy_ml ntuples/energy_ml_stage110
stage110_status=0
/usr/bin/time -v -o workbook/stage110_energy_ml/time.txt timeout --signal=TERM --kill-after=5 850 python -u ml/stage110_transfer.py || stage110_status=$?
tar -czf result.tar.gz workbook/stage110_energy_ml ntuples/energy_ml_stage110
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage110/result.tar.gz
exit "$stage110_status"
