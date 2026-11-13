#!/usr/bin/env bash
# One reconstruction, three paired makers; retain compact diagnostics only.
set -eo pipefail
index="$1"
rdo="$2"
nevents="${3:--1}"
result="$4"
skip="${5:-0}"
debug="${6:-0}"
tracking_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_geo201.XXXXXX")
trap 'rm -rf "$tracking_scratch"' EXIT
tracking_launch="$PWD"
mkdir -p "$tracking_scratch/code" "$tracking_scratch/runtime"
tar -xzf "$tracking_launch/tracking-georotation-code.tar.gz" -C "$tracking_scratch/code"
cd "$tracking_scratch"
stage() {
    local name="$1"
    shift
    if /usr/bin/time -o "$name.time" -f "$name wall_seconds=%e max_rss_kib=%M user_seconds=%U system_seconds=%S" \
        "$@" > "$name.log" 2>&1; then
        cat "$name.time"
    else
        cat "$name.time"
        if command -v rg >/dev/null; then
            rg -a -m 60 'ERROR|FATAL|[Ss]ignal|[Ss]egmentation|^#0 |^#1 |^#2 ' "$name.log" || true
        else
            grep -a -m 60 -E 'ERROR|FATAL|[Ss]ignal|[Ss]egmentation|^#0 |^#1 |^#2 ' "$name.log" || true
        fi
        if [[ -f eventLoopHeartBeat.txt ]]; then tail -n 4 eventLoopHeartBeat.txt; fi
        tail -n 90 "$name.log"
        gzip -c "$name.log" > failure.log.gz
        xrdcp --silent --force failure.log.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_georotation_stage201/failure_${index}_${skip}_${name}.log.gz" || true
        if [[ "$debug" == 1 && -f input-xAOD.root ]]; then
            xrdcp --silent --force input-xAOD.root "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_georotation_stage201/failure_${index}_${skip}_xAOD.root" || true
        fi
        return 1
    fi
}
stage runtime_copy xrdcp --silent root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/software/stage201_tracking/calypso_reco_runtime.tar.gz runtime.tar.gz
stage runtime_unpack tar -xzf runtime.tar.gz -C runtime
rm runtime.tar.gz
export NU_MU_SKIP_LCG=1 FASER_CALYPSO_RUN="$tracking_scratch/runtime"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
source "$tracking_scratch/code/setup_env.sh"
nu_mu_calypso_setup
export ROOT_INCLUDE_PATH="$FASER_CALYPSO_RUN/include:${ROOT_INCLUDE_PATH:-}"
stage input xrdcp --silent "root://eospublic.cern.ch/$rdo" input-RDO.root
stage reco python "$tracking_scratch/code/AnalysisZipFramework/scripts/run_tracking_georotation.py" reco input-RDO.root --nevents "$nevents" --skip "$skip"
for mode in forward backward; do
    if [[ "$debug" == 1 ]]; then
        stage "$mode" python "$tracking_scratch/code/AnalysisZipFramework/scripts/run_tracking_georotation.py" "$mode" input-xAOD.root --nevents "$nevents" --event-log
    else
        stage "$mode" faser_ntuple_maker.py --isMC --geom TI12MC04 --cond OFLCOND-FASER-06 --CKFTrackType "$mode" \
            --nevents "$nevents" --outfile "$mode.root" input-xAOD.root
    fi
done
stage merge python "$tracking_scratch/code/AnalysisZipFramework/scripts/run_tracking_georotation.py" merge input-xAOD.root --nevents "$nevents"
stage extract python "$tracking_scratch/code/AnalysisZipFramework/scripts/extract_tracking_georotation.py" \
    --repo "$tracking_scratch/code" --index "$index" --output result.npz
cat extract.log
python - <<'PY'
import json, pathlib, socket
import numpy as np
with np.load('result.npz') as source:
    result = {key: source[key] for key in source.files}
result['effective_reco_json'] = pathlib.Path('effective_reco.json').read_text()
result['performance_json'] = json.dumps({p.stem: p.read_text().strip() for p in pathlib.Path('.').glob('*.time')})
result['software_provenance_json'] = pathlib.Path('code/workbook/stage201_tracking/software_provenance.json').read_text()
result['host'] = socket.gethostname()
result['root_file_bytes_json'] = json.dumps({p.name: p.stat().st_size for p in pathlib.Path('.').glob('*.root')})
np.savez_compressed('result.npz', **result)
PY
stage upload xrdcp --silent --force result.npz "root://eoshome-x.cern.ch/$result"
echo "completed index=$index nevents=$nevents result=$result"
