#!/usr/bin/env bash
set -eo pipefail
stage66_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_trainingout.XXXXXX")
trap 'rm -rf "$stage66_scratch"' EXIT
tar -xzf energy-ml-trainingout-stage66.tar.gz -C "$stage66_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage66_status=0
/usr/bin/time -f 'trainingout wall_s=%e user_s=%U system_s=%S max_rss_KiB=%M' \
    python -u "$stage66_scratch/ml/run_trainingout_response.py" || stage66_status=$?
stage66_archive="$stage66_scratch/results.tar.gz"
tar -czf "$stage66_archive" -C "$stage66_scratch" workbook/stage66_energy_ml
xrdcp --silent "$stage66_archive" \
    root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage66/results.tar.gz
exit "$stage66_status"
