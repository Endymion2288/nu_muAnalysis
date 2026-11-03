#!/usr/bin/env bash
set -eo pipefail
stage69_pair=$1
stage69_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_transfer.XXXXXX")
trap 'rm -rf "$stage69_scratch"' EXIT
tar -xzf energy-ml-transfer-supervision-stage69.tar.gz -C "$stage69_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage69_status=0
/usr/bin/time -f 'transfer wall_s=%e user_s=%U system_s=%S max_rss_KiB=%M' \
    python -u "$stage69_scratch/ml/fit_transfer_supervision.py" --job "$stage69_pair" || stage69_status=$?
stage69_items=(workbook/stage69_energy_ml)
if [ -d "$stage69_scratch/ml/artifacts/stage69" ]; then stage69_items+=(ml/artifacts/stage69); fi
tar -czf "$stage69_scratch/results.tar.gz" -C "$stage69_scratch" "${stage69_items[@]}"
xrdcp --silent "$stage69_scratch/results.tar.gz" \
    "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage69/$stage69_pair.tar.gz"
exit "$stage69_status"
