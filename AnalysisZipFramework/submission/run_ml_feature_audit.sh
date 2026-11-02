#!/bin/bash
set -eo pipefail
stage56_mode="$1"
stage56_batch="${2:-0}"
stage56_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_feature_audit.XXXXXX")
trap 'rm -rf "$stage56_scratch"' EXIT
tar -xzf energy-ml-feature-audit-stage56.tar.gz -C "$stage56_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
if [[ "$stage56_mode" == read ]]; then
    /usr/bin/time -f 'read wall_s=%e user_s=%U system_s=%S rss_KiB=%M' \
        python "$stage56_scratch/ml/read_audited_features.py" --batch "$stage56_batch" --output "$stage56_scratch/readout.npz"
    xrdcp --silent "$stage56_scratch/readout.npz" "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage56/shards/${stage56_batch}.npz"
elif [[ "$stage56_mode" == train ]]; then
    /usr/bin/time -f 'train wall_s=%e user_s=%U system_s=%S rss_KiB=%M' \
        python "$stage56_scratch/ml/train_audited_features.py"
    tar -czf "$stage56_scratch/models.tar.gz" -C "$stage56_scratch" ml/artifacts/stage56
    xrdcp --silent "$stage56_scratch/models.tar.gz" root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage56/models.tar.gz
else
    exit 2
fi
