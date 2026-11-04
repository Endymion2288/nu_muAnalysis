#!/usr/bin/env bash
set -eo pipefail
stage105_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage105.XXXXXX")
trap 'rm -rf "$stage105_scratch"' EXIT
tar -xzf energy-ml-stage105.tar.gz -C "$stage105_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
cd "$stage105_scratch"
stage105_status=0
/usr/bin/time -v -o workbook/stage105_energy_ml/time.txt timeout --signal=TERM --kill-after=5 850 python -u ml/stage105_point_feasibility.py || stage105_status=$?
tar -czf result.tar.gz workbook/stage105_energy_ml
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage105/result.tar.gz
exit "$stage105_status"
