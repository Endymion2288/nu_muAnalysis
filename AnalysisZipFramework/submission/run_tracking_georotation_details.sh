#!/usr/bin/env bash
set -eo pipefail
index="$1"; run="$2"; event="$3"; rdo="$4"; old_merge="$5"; reference="$6"; result="$7"
detail_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_geo201_detail.XXXXXX")
trap 'rm -rf "$detail_scratch"' EXIT
mkdir "$detail_scratch/code" "$detail_scratch/runtime"
tar -xzf tracking-georotation-code.tar.gz -C "$detail_scratch/code"
cd "$detail_scratch"
stage() {
    local name="$1"
    shift
    if /usr/bin/time -o "$name.time" -f "$name wall_seconds=%e max_rss_kib=%M user_seconds=%U system_seconds=%S" \
        "$@" > "$name.log" 2>&1; then
        cat "$name.time"
    else
        cat "$name.time"
        grep -a -m 30 -E 'ERROR|FATAL|[Ss]ignal|^#0 |^#1 |^#2 ' "$name.log" || true
        tail -n 40 "$name.log"
        return 1
    fi
}
stage runtime_copy xrdcp --silent root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/software/stage201_tracking/calypso_reco_runtime.tar.gz runtime.tar.gz
stage runtime_unpack tar -xzf runtime.tar.gz -C runtime
rm runtime.tar.gz
export NU_MU_SKIP_LCG=1 FASER_CALYPSO_RUN="$detail_scratch/runtime"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
source "$detail_scratch/code/setup_env.sh"
nu_mu_calypso_setup
export ROOT_INCLUDE_PATH="$FASER_CALYPSO_RUN/include:${ROOT_INCLUDE_PATH:-}"
stage reference xrdcp --silent "root://eoshome-x.cern.ch/$reference" reference.npz
stage locate python "$detail_scratch/code/AnalysisZipFramework/scripts/locate_tracking_event.py" \
    --ntuple "$old_merge" --rdo "$rdo" --run "$run" --event "$event" --output entry.txt
entry=$(cat entry.txt)
stage input xrdcp --silent "root://eospublic.cern.ch/$rdo" input-RDO.root
stage reco python "$detail_scratch/code/AnalysisZipFramework/scripts/run_tracking_georotation.py" reco input-RDO.root --skip "$entry" --nevents 1
for mode in forward backward; do
    stage "$mode" faser_ntuple_maker.py --isMC --geom TI12MC04 --cond OFLCOND-FASER-06 \
        --CKFTrackType "$mode" --nevents 1 --outfile "$mode.root" input-xAOD.root
done
stage merge python "$detail_scratch/code/AnalysisZipFramework/scripts/run_tracking_georotation.py" merge input-xAOD.root --nevents 1 --details
stage extract python "$detail_scratch/code/AnalysisZipFramework/scripts/extract_tracking_georotation_details.py" \
    --repo "$detail_scratch/code" --reference reference.npz --run "$run" --event "$event" --output result.json
cat extract.log
python - <<'PY'
import json,pathlib,socket
p=pathlib.Path('result.json');r=json.loads(p.read_text())
r['performance']={p.stem:p.read_text().strip() for p in pathlib.Path('.').glob('*.time')}
r['host']=socket.gethostname();r['entry']=int(pathlib.Path('entry.txt').read_text())
r['effective_reco']=json.loads(pathlib.Path('effective_reco.json').read_text())
p.write_text(json.dumps(r,allow_nan=True,separators=(',',':')))
PY
stage upload xrdcp --silent --force result.json "root://eoshome-x.cern.ch/$result"
echo "completed detail index=$index event=$run/$event"
