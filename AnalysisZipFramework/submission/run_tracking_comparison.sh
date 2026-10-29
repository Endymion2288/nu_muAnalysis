#!/usr/bin/env bash
# Reconstruct once; make all three default track modes from exactly that xAOD.
set -eo pipefail
index="$1"
rdo="$2"
geometry="$3"
existing_merge="$4"
report="$5"
repo="$6"
payload="$7"
nevents="${8:--1}"
product="${9:-cutflow}"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_compare.XXXXXX")
partial=""
endpoint=root://eoshome-x.cern.ch
cleanup() {
    rm -rf "$scratch"
    if [[ -n "$partial" ]]; then xrdfs "$endpoint" rm "$partial" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT
mkdir -p "$scratch/code"
tar -xzf "$payload" -C "$scratch/code"
export NU_MU_SKIP_LCG=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source "$scratch/code/setup_env.sh"
nu_mu_official_setup "$scratch/runtime"
cd "$scratch"
echo "index=$index host=$(hostname) input=$rdo existing_merge=$existing_merge nevents=$nevents"
cat "$FASER_CALYPSO_RUN/NU_MU_BUILD_INFO.txt"
if [[ -f "$report" ]] && python - "$report" "$product" <<'PY'
import sys
import numpy as np
with np.load(sys.argv[1]) as result:
    assert result['counts'].shape == (3, 21)
    if sys.argv[2] == 'fiducial':
        assert int(result['reference_verified']) == 1
        assert result['event_cut_bits'].shape[1] == 3
    else:
        assert result['energy_pass'].shape[-1] == 11
        assert int(result['existing_merge_verified']) == 1
PY
then
    echo "valid paired summary already exists; skipping"
    exit 0
fi
stage() {
    local name="$1"
    shift
    if /usr/bin/time -o "$name.time" -f "$name wall_seconds=%e max_rss_kib=%M user_seconds=%U system_seconds=%S" \
            "$@" > "$name.log" 2>&1; then
        cat "$name.time"
    else
        cat "$name.time"
        tail -n 100 "$name.log"
        return 1
    fi
}
stage input cp "$rdo" .
local_rdo=$(basename "$rdo")
stage reco faser_reco.py --isMC --geom "$geometry" --nevents "$nevents" "$local_rdo"
xaod="${local_rdo%-RDO.root}-xAOD.root"
modes=(forward backward merge)
if [[ "$product" == fiducial ]]; then
    stage existing_merge cp "$existing_merge" merge.root
    modes=(forward backward)
fi
for mode in "${modes[@]}"; do
    stage "$mode" faser_ntuple_maker.py --isMC --geom "$geometry" --CKFTrackType "$mode" \
        --nevents "$nevents" --outfile "$mode.root" "$xaod"
done
# Use the existing merge only after all modes share the same new reconstruction.
comparison=(python "$scratch/code/AnalysisZipFramework/scripts/compare_tracking.py"
    --repo "$scratch/code" --forward forward.root --backward backward.root --merge merge.root
    --output result.npz --threads 1)
result_file=result.npz
if [[ "$product" == fiducial ]]; then
    comparison+=(--reference "$scratch/code/reference.npz" --index "$index"
        --fiducial-output fiducial.npz)
    result_file=fiducial.npz
else
    comparison+=(--existing-merge "$existing_merge")
fi
stage comparison "${comparison[@]}"
cat comparison.log
partial="${report}.partial.$$"
xrdcp --force --silent "$result_file" "$endpoint/$partial"
local_bytes=$(stat -c '%s' "$result_file")
remote_bytes=$(xrdfs "$endpoint" stat "$partial" | awk '$1=="Size:" {print $2}')
[[ "$local_bytes" == "$remote_bytes" ]] || exit 1
xrdfs "$endpoint" mv "$partial" "$report"
partial=""
echo "completed index=$index report=$report bytes=$local_bytes"
