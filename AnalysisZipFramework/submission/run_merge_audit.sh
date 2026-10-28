#!/usr/bin/env bash
set -eo pipefail
repo="$1"
archive="$2"
manifest="$3"
report="$4"
workers="${5:-4}"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_audit.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
export NU_MU_SKIP_LCG=1 FASER_OFFICIAL_ARCHIVE="$archive"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source "$repo/setup_env.sh"
nu_mu_official_setup "$scratch/runtime"
/usr/bin/time -f 'audit wall_seconds=%e max_rss_kib=%M user_seconds=%U system_seconds=%S' \
    python "$repo/AnalysisZipFramework/submission/audit_merge_production.py" \
    --manifest "$manifest" --output "$report" --workers "$workers"
