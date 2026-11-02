#!/usr/bin/env bash
set -eo pipefail
stage64_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_migration.XXXXXX")
trap 'rm -rf "$stage64_scratch"' EXIT
tar -xzf energy-ml-migration-stage64.tar.gz -C "$stage64_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage64_status=0
/usr/bin/time -f 'migration wall_s=%e user_s=%U system_s=%S max_rss_KiB=%M' \
    python -u "$stage64_scratch/ml/run_response_migration.py" || stage64_status=$?
stage64_archive="$stage64_scratch/results.tar.gz"
tar -czf "$stage64_archive" -C "$stage64_scratch" workbook/stage64_energy_ml
xrdcp --silent "$stage64_archive" \
    root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage64/results.tar.gz
exit "$stage64_status"
