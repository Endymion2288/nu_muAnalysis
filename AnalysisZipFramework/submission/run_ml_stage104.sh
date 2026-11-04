#!/usr/bin/env bash
set -eo pipefail
stage104_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage104.XXXXXX")
trap 'rm -rf "$stage104_scratch"' EXIT
tar -xzf energy-ml-stage104.tar.gz -C "$stage104_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
cd "$stage104_scratch"
mkdir -p workbook/stage104_energy_ml ntuples/energy_ml_stage104
stage104_status=0
/usr/bin/time -v -o workbook/stage104_energy_ml/time.txt timeout --signal=TERM --kill-after=5 850 python -u ml/stage104_decision.py || stage104_status=$?
tar -czf result.tar.gz workbook/stage104_energy_ml ntuples/energy_ml_stage104
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage104/result.tar.gz
exit "$stage104_status"
