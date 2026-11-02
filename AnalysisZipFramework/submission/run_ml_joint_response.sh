#!/usr/bin/env bash
set -eo pipefail
stage63_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_joint.XXXXXX")
trap 'rm -rf "$stage63_scratch"' EXIT
tar -xzf energy-ml-joint-stage63.tar.gz -C "$stage63_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
stage63_status=0
/usr/bin/time -f 'joint wall_s=%e user_s=%U system_s=%S max_rss_KiB=%M' \
    python -u "$stage63_scratch/ml/run_joint_response.py" || stage63_status=$?
stage63_archive="$stage63_scratch/results.tar.gz"
tar -czf "$stage63_archive" -C "$stage63_scratch" workbook/stage63_energy_ml
xrdcp --silent "$stage63_archive" \
    root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage63/results.tar.gz
exit "$stage63_status"
