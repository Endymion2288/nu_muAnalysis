#!/usr/bin/env bash
set -eo pipefail
stage65_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_hardness.XXXXXX")
trap 'rm -rf "$stage65_scratch"' EXIT
tar -xzf energy-ml-hardness-stage65.tar.gz -C "$stage65_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage65_status=0
/usr/bin/time -f 'hardness wall_s=%e user_s=%U system_s=%S max_rss_KiB=%M' \
    python -u "$stage65_scratch/ml/run_spectrum_hardness.py" || stage65_status=$?
stage65_archive="$stage65_scratch/results.tar.gz"
tar -czf "$stage65_archive" -C "$stage65_scratch" workbook/stage65_energy_ml
xrdcp --silent "$stage65_archive" \
    root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage65/results.tar.gz
exit "$stage65_status"
