#!/usr/bin/env bash
set -eo pipefail
if [ "${1:-}" != --worker ]; then
    exec /usr/bin/time -f 'stage32 wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' "$0" --worker "$@"
fi
shift
action="$1"; index="$2"; payload="$3"; repository="$4"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_reference.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
mkdir -p "$scratch/code"
tar -xzf "$payload" -C "$scratch/code"
export NU_MU_SKIP_LCG=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source "$scratch/code/setup_env.sh"
nu_mu_official_setup "$scratch/runtime"
cd "$scratch"
request="$scratch/code/ntuples/energy_ml_stage32/requests/$index.json"
stage() {
    local name="$1"; shift
    if /usr/bin/time -o "$name.time" -f 'wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' timeout 600 "$@" > "$name.log" 2>&1; then
        echo "$name $(cat "$name.time")"
    else
        tail -70 "$name.log"; return 1
    fi
}
if [ "$action" = truth ]; then
    stage truth python "$scratch/code/ml/audit_transport_truth.py" --request "$request" --output result.json
else
    input=$(python -c 'import json,sys;print(json.load(open(sys.argv[1]))["row"]["input_rdo"])' "$request")
    stage copy cp "$input" input-RDO.root
    mapfile -t entries < <(python -c 'import json,sys;[print(e["eventID"],e["entry"]) for e in json.load(open(sys.argv[1]))["events"] if e["covariance_requested"]]' "$request")
    for entry in "${entries[@]}"; do
        read -r event offset <<< "$entry"
        stage "reco_$event" faser_reco.py --isMC --geom TI12MC04 --skip "$offset" --nevents 1 input-RDO.root
        stage "cov_$event" python "$scratch/code/ml/audit_reference_covariance.py" --request "$request" --event "$event" --xaod input-xAOD.root --output "cov_$event.json"
        rm -f input-xAOD.root audit-ntuple.root
    done
    python - "$request" <<'PY'
import glob,json,sys
request=json.load(open(sys.argv[1]));parts=[json.load(open(p)) for p in sorted(glob.glob('cov_*.json'))]
assert len(parts)==request['cfg']['covariance_events_per_file']
result=dict(index=int(request['row']['index']),events=sum([p['events'] for p in parts],[]),stage_timings={p:open(p).read().strip() for p in glob.glob('*.time')},export_wall_s=sum(p['wall_s'] for p in parts),export_cpu_s=sum(p['cpu_s'] for p in parts),export_peak_rss_MiB=max(p['peak_rss_MiB'] for p in parts))
json.dump(result,open('result.json','w'),separators=(',',':'))
PY
fi
endpoint=root://eoshome-x.cern.ch
destination="$repository/ntuples/energy_ml_stage32/$action/$index.json"
xrdcp -f --silent result.json "$endpoint/$destination"
