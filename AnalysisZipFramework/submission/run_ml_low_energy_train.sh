#!/bin/bash
set -eo pipefail
stage55_train_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_low_energy_train.XXXXXX")
trap 'rm -rf "$stage55_train_scratch"' EXIT
tar -xzf energy-ml-low-energy-train-stage55.tar.gz -C "$stage55_train_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
for stage55_train_model in nominal100 nominal50 mixture50 residual50 matched_flux50; do
    for stage55_train_seed in 0 1 2; do
        /usr/bin/time -f 'train wall_s=%e user_s=%U system_s=%S max_rss_KiB=%M' \
            python "$stage55_train_scratch/ml/train_low_energy.py" --model "$stage55_train_model" --seed "$stage55_train_seed"
    done
done
tar -czf "$stage55_train_scratch/models.tar.gz" -C "$stage55_train_scratch" ml/artifacts/stage55
xrdcp --silent --force "$stage55_train_scratch/models.tar.gz" root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage55/models.tar.gz
