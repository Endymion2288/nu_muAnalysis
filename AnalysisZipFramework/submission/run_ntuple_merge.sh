#!/usr/bin/env bash
set -eo pipefail

input_dir="$1"
slice="$2"
geometry="$3"
outfile="$4"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
workdir="${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_merge_${slice}_$$"

export NU_MU_SKIP_LCG=1
source "${repo_root}/setup_env.sh"
nu_mu_calypso_setup
set -u

# Athena writes PoolFileCatalog.xml and event-loop diagnostics in the current
# directory.  Keep those transient files on the worker scratch disk so jobs
# never race through the shared EOS checkout.
mkdir -p "${workdir}"
cd "${workdir}"

mkdir -p "$(dirname "${outfile}")"
echo "host=$(hostname)"
echo "input_dir=${input_dir} slice=${slice} geometry=${geometry}"
echo "output=${outfile}"

# A completed output is the only persistent job state.  This keeps retries
# idempotent and avoids duplicate JSON or log products on EOS.
if [[ -s "${outfile}" ]]; then
    echo "output already exists; skipping"
    exit 0
fi

maker_args=("${input_dir}" --slice "${slice}" --files 1 --merge 10
    --geom "${geometry}" --isMC --CKFTrackType merge --outfile "${outfile}")
if [[ -n "${NTUPLE_NEVENTS:-}" ]]; then
    maker_args+=(--nevents "${NTUPLE_NEVENTS}")
fi
faser_ntuple_maker.py "${maker_args[@]}"

test -s "${outfile}"
echo "completed bytes=$(stat -c '%s' "${outfile}")"
