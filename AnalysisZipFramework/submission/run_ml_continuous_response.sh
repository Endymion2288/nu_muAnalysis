#!/usr/bin/env bash
set -eo pipefail
stage62_model="$1"
stage62_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_continuous.XXXXXX")
trap 'rm -rf "$stage62_scratch"' EXIT
tar -xzf energy-ml-continuous-stage62.tar.gz -C "$stage62_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
/usr/bin/time -f 'continuous wall_s=%e user_s=%U system_s=%S max_rss_KiB=%M' \
    python -u "$stage62_scratch/ml/fit_continuous_response.py" --model "$stage62_model"
stage62_archive="$stage62_scratch/$stage62_model.tar.gz"
tar -czf "$stage62_archive" -C "$stage62_scratch" \
    "ml/artifacts/stage62/$stage62_model" "workbook/stage62_energy_ml/$stage62_model"
xrdcp --silent "$stage62_archive" \
    "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage62/$stage62_model.tar.gz"
