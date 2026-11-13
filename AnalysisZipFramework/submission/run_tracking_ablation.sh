#!/usr/bin/env bash
set -eo pipefail
index="$1"; variant="$2"; rdo="$3"; nevents="$4"; skip="$5"; result="$6"
version=new
if [[ "$variant" == old ]]; then version=old; fi
station_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_ablation204.XXXXXX")
trap 'rm -rf "$station_scratch"' EXIT
mkdir "$station_scratch/code" "$station_scratch/runtime"
tar -xzf tracking-station-code.tar.gz -C "$station_scratch/code"
cd "$station_scratch"
cp code/material-rotated.json material-rotated.json
stage() {
    local name="$1"; shift
    if /usr/bin/time -o "$name.time" -f "$name wall_seconds=%e max_rss_kib=%M user_seconds=%U system_seconds=%S" "$@" > "$name.log" 2>&1; then cat "$name.time"
    else
        cat "$name.time"
        grep -n -m 12 -E 'ERROR|FATAL|signal|Segmentation|EventLoop|crash' "$name.log" || true
        tail -n 120 "$name.log"
        return 1
    fi
}
endpoint=root://eoshome-x.cern.ch
if [[ "$version" == new ]]; then archive=/eos/user/x/xcheng/FASER/nu_muAnalysis/software/stage201_tracking/calypso_reco_runtime.tar.gz
else archive=/eos/user/x/xcheng/FASER/nu_muAnalysis/software/calypso-master-d32b0ff3-el9-gcc13.tar.gz; fi
stage runtime_copy xrdcp --silent "$endpoint/$archive" runtime.tar.gz
stage runtime_unpack tar -xzf runtime.tar.gz -C runtime
rm runtime.tar.gz
export NU_MU_SKIP_LCG=1 FASER_CALYPSO_RUN="$station_scratch/runtime"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
source "$station_scratch/code/setup_env.sh"
nu_mu_calypso_setup
export ROOT_INCLUDE_PATH="$FASER_CALYPSO_RUN/include:${ROOT_INCLUDE_PATH:-}"
stage input xrdcp --silent "root://eospublic.cern.ch/$rdo" input-RDO.root
if [[ "$version" == old ]]; then
    stage reco python code/AnalysisZipFramework/scripts/run_tracking_station.py reco old input-RDO.root --nevents "$nevents" --skip "$skip"
else
    stage reco python code/AnalysisZipFramework/scripts/run_tracking_ablation.py "$variant" input-RDO.root --nevents "$nevents" --skip "$skip"
fi
if [[ "${TRACKING_ABLATION_AUDIT:-0}" == 1 && "$version" == new ]]; then
    stage audit python code/AnalysisZipFramework/scripts/extract_tracking_ablation_audit.py
fi
for mode in forward backward; do
    maker=(faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType "$mode" --nevents "$nevents" --outfile "$mode.root")
    if [[ "$version" == new ]]; then maker+=(--cond OFLCOND-FASER-06); fi
    stage "$mode" "${maker[@]}" input-xAOD.root
done
stage merge python code/AnalysisZipFramework/scripts/run_tracking_station.py merge "$version" input-xAOD.root --nevents "$nevents"
if [[ "${TRACKING_ABLATION_WAVEFORM:-0}" == 1 ]]; then
    stage waveform python code/AnalysisZipFramework/scripts/extract_tracking_waveform.py
fi
stage extract python code/AnalysisZipFramework/scripts/extract_tracking_station.py --repo code --version "$version" --index "$index" --output result.npz
cat extract.log
ABLATION_VARIANT="$variant" python - <<'PY'
import json,pathlib,socket,os
import numpy as np
with np.load('result.npz') as f:a={k:f[k] for k in f.files}
a['performance_json']=json.dumps({p.stem:p.read_text().strip() for p in pathlib.Path('.').glob('*.time')})
a['host']=socket.gethostname()
a['variant']=os.environ['ABLATION_VARIANT']
a['effective_ablation_json']=pathlib.Path('effective_ablation.json').read_text() if pathlib.Path('effective_ablation.json').exists() else a['effective_reco_json'] if 'effective_reco_json' in a else 'official old defaults'
a['root_bytes_json']=json.dumps({p.name:p.stat().st_size for p in pathlib.Path('.').glob('*.root')})
a['effective_reco_json']=pathlib.Path('effective_reco.json').read_text() if pathlib.Path('effective_reco.json').exists() else 'official d32b0ff3 defaults; OFLCOND-FASER-06'
if pathlib.Path('audit_summary.json').exists():
    a['audit_summary_json']=pathlib.Path('audit_summary.json').read_text()
    with np.load('audit_rows.npz') as f:
        for k in f.files:a['audit_'+k]=f[k]
if pathlib.Path('waveform.npz').exists():
    with np.load('waveform.npz') as f:
        for k in f.files:a['waveform_'+k]=f[k]
np.savez_compressed('result.npz',**a)
PY
stage upload xrdcp --silent --force result.npz "$endpoint/$result"
echo "completed ablation index=$index variant=$variant skip=$skip"
