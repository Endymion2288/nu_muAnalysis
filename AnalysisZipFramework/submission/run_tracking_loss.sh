#!/usr/bin/env bash
# Reconstruct one selected event; keep no RDO/xAOD/ntuple intermediates.
set -eo pipefail
run="$1"
event="$2"
rdo="$3"
merge="$4"
report="$5"
payload="$6"
forward_bits="$7"
backward_bits="$8"
merge_bits="$9"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_loss.XXXXXX")
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
nu_mu_official_setup "${NU_MU_LOSS_RUNTIME:-$scratch/runtime}"
cd "$scratch"
if [[ -f "$report" ]] && python - "$report" "$run" "$event" "$forward_bits" "$backward_bits" "$merge_bits" <<'PY'
import json, sys
with open(sys.argv[1]) as source:
    event = json.load(source)
assert event['run'] == int(sys.argv[2]) and event['event'] == int(sys.argv[3])
assert event['expected_bits'] == list(map(int, sys.argv[4:7]))
assert event['existing_merge_verified']
PY
then
    echo "validated existing diagnostic; skipping run=$run event=$event"
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
        tail -n 70 "$name.log"
        return 1
    fi
}
echo "run=$run event=$event host=$(hostname)"
stage locate python - "$merge" "$run" "$event" "$scratch/code/AnalysisZipFramework/scripts" <<'PY'
import sys
sys.path.insert(0, sys.argv[4])
from extract_tracking_loss import locate
print(locate(sys.argv[1], int(sys.argv[2]), int(sys.argv[3])))
PY
entry=$(tail -n 1 locate.log)
stage input cp "$rdo" input-RDO.root
stage reco faser_reco.py --isMC --geom TI12MC04 --skip "$entry" --nevents 1 input-RDO.root
for mode in forward backward; do
    stage "$mode" faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType "$mode" \
        --nevents 1 --outfile "$mode.root" input-xAOD.root
done
stage merge python "$scratch/code/AnalysisZipFramework/scripts/inspect_tracking_loss.py" input-xAOD.root
stage extract python "$scratch/code/AnalysisZipFramework/scripts/extract_tracking_loss.py" \
    --repo "$scratch/code" --run "$run" --event "$event" \
    --bits "$forward_bits" "$backward_bits" "$merge_bits" --existing-merge "$merge" --output event.json
cat extract.log
partial="${report}.partial.$$"
xrdcp --force --silent event.json "$endpoint/$partial"
local_bytes=$(stat -c '%s' event.json)
remote_bytes=$(xrdfs "$endpoint" stat "$partial" | awk '$1=="Size:" {print $2}')
[[ "$local_bytes" == "$remote_bytes" ]]
xrdfs "$endpoint" mv "$partial" "$report"
partial=""
echo "completed run=$run event=$event bytes=$local_bytes"
