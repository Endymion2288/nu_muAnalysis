#!/usr/bin/env bash
# Triggered by the DAG only after the independently submitted extraction finishes.
set -eo pipefail
payload="$1"
reports="$2"
models="$3"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_bdt.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code" "$scratch/reports" "$scratch/models"
tar -xzf "$payload" -C "$scratch/code"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONNOUSERSITE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
endpoint=root://eoshome-x.cern.ch
xrdfs "$endpoint" mkdir -p "$reports"
xrdfs "$endpoint" mkdir -p "$models"
# QA aggregation creates one cache per partition and verifies them before removing shards.
if [[ ! -f "$reports/extraction_summary.json" ]]; then
    /usr/bin/time -f 'aggregate wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        python3 -u "$scratch/code/ml/audit_dataset.py" --repo "$scratch/code" \
        --output-dir "$scratch/reports" --remove-shards
    for file in "$scratch/reports/"*; do
        xrdcp -f --silent "$file" "$endpoint/$reports/$(basename "$file")"
    done
fi
/usr/bin/time -f 'bdt wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
    python3 -u "$scratch/code/ml/train_bdt.py" --repo "$scratch/code" \
    --output-dir "$scratch/reports" --model-dir "$scratch/models"
python3 "$scratch/code/ml/plot_bdt.py" --report-dir "$scratch/reports" --model-dir "$scratch/models"
for file in "$scratch/reports/"*; do
    xrdcp -f --silent "$file" "$endpoint/$reports/$(basename "$file")"
done
for file in "$scratch/models/"*; do
    xrdcp -f --silent "$file" "$endpoint/$models/$(basename "$file")"
done
