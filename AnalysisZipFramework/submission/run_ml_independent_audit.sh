#!/usr/bin/env bash
set -eo pipefail
model="$1"
seed="$2"
alpha_index="$3"
payload="$4"
repository="$5"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_independent_audit.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/results"
tar -xzf "$payload" -C "$scratch/code"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
/usr/bin/time -f 'independent_audit wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
    python3 -u "$scratch/code/ml/audit_independent_starts.py" --repo "$scratch/code" \
    --model "$model" --seed-index "$seed" --alpha-index "$alpha_index" --output-dir "$scratch/results"
destination="$repository/workbook/stage27_energy_ml/start_audits"
xrdfs root://eoshome-x.cern.ch mkdir -p "$destination"
xrdcp -f --silent "$scratch/results/start_audit.json" \
    "root://eoshome-x.cern.ch/$destination/${model}_seed_${seed}_alpha_${alpha_index}.json"
