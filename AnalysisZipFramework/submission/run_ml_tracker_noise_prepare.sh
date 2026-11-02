#!/bin/bash
set -eo pipefail
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_noise_prepare.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
tar -xzf energy-ml-tracker-noise-prepare-stage53.tar.gz -C "$scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
timeout 600s python "$scratch/ml/prepare_tracker_noise.py" --output "$scratch/sample.json"
xrdcp -f --silent "$scratch/sample.json" root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage53/sample.json
