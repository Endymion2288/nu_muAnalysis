#!/usr/bin/env bash
set -eo pipefail
stage68_pair=$1
stage68_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_risk.XXXXXX")
trap 'rm -rf "$stage68_scratch"' EXIT
tar -xzf energy-ml-group-risk-stage68.tar.gz -C "$stage68_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage68_status=0
/usr/bin/time -f 'risk wall_s=%e user_s=%U system_s=%S max_rss_KiB=%M' \
    python -u "$stage68_scratch/ml/fit_group_risk.py" --job "$stage68_pair" || stage68_status=$?
stage68_items=(workbook/stage68_energy_ml)
if [ -d "$stage68_scratch/ml/artifacts/stage68" ]; then stage68_items+=(ml/artifacts/stage68); fi
tar -czf "$stage68_scratch/results.tar.gz" -C "$stage68_scratch" "${stage68_items[@]}"
xrdcp --silent "$stage68_scratch/results.tar.gz" \
    "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage68/$stage68_pair.tar.gz"
exit "$stage68_status"
