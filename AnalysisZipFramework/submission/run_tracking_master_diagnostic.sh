#!/usr/bin/env bash
set -eo pipefail
index="$1"; rdo="$2"; nevents="$3"; skip="$4"; result="$5"
export STAGE209_CONTROL="$6"
export CALYPSO_DIAG_EVENTS="$7"
audit_library="$8"
paired_old=0
export INTEGRATION_PAIRED_ORDER=latest_only
if [[ "$paired_old" == 1 ]]; then
    if (( index % 2 == 0 )); then export INTEGRATION_PAIRED_ORDER=old_first
    else export INTEGRATION_PAIRED_ORDER=latest_first; fi
fi
integration_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_causes209.XXXXXX")
trap 'rm -rf "$integration_scratch"' EXIT
mkdir "$integration_scratch/code" "$integration_scratch/runtime"
tar -xzf code.tar.gz -C "$integration_scratch/code"
cd "$integration_scratch"
stage() {
    local name="$1"; shift
    if /usr/bin/time -o "$name.time" -f "$name wall_seconds=%e max_rss_kib=%M user_seconds=%U system_seconds=%S" "$@" > "$name.log" 2>&1; then
        cat "$name.time"
    else
        cat "$name.time"
        rg -n -m 12 'ERROR|FATAL|signal|Segmentation|EventLoop|crash|Traceback' "$name.log" || true
        tail -n 100 "$name.log"
        return 1
    fi
}
endpoint=root://eoshome-x.cern.ch
stage runtime_copy xrdcp --silent "$endpoint//eos/user/x/xcheng/FASER/nu_muAnalysis/software/stage208_master/calypso_runtime.tar.gz" runtime.tar.gz
stage runtime_unpack tar -xzf runtime.tar.gz -C runtime
rm runtime.tar.gz
cmp code/software_provenance.json runtime/software_provenance.json
if [[ "$audit_library" != 0 ]]; then
    diagnostic_library=libFaserActsKalmanFilter.so
    if [[ "$audit_library" == 2 ]]; then diagnostic_library=libFaserActsKalmanFilter.seedstarts.so; fi
    xrdcp --silent --force "$endpoint//eos/user/x/xcheng/FASER/nu_muAnalysis/software/stage209_diagnostic/$diagnostic_library" runtime/lib/libFaserActsKalmanFilter.so
fi
cp code/material-strict-reference.json.gz .
stage input xrdcp --silent "root://eospublic.cern.ch/$rdo" input-RDO.root
(
export NU_MU_SKIP_LCG=1 FASER_CALYPSO_RUN="$integration_scratch/runtime"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
source "$integration_scratch/code/setup_env.sh"
nu_mu_calypso_setup
export ROOT_INCLUDE_PATH="$FASER_CALYPSO_RUN/include:${ROOT_INCLUDE_PATH:-}"
stage reco python code/AnalysisZipFramework/scripts/run_tracking_master_diagnostic.py input-RDO.root --nevents "$nevents" --skip "$skip"
for mode in forward backward; do
    stage "$mode" faser_ntuple_maker.py --isMC --geom TI12MC04 --cond OFLCOND-FASER-06 --CKFTrackType "$mode" --nevents "$nevents" --outfile "$mode.root" input-xAOD.root
done
stage merge python code/AnalysisZipFramework/scripts/run_tracking_station.py merge new input-xAOD.root --nevents "$nevents"
stage extract python code/AnalysisZipFramework/scripts/extract_tracking_station.py --repo code --version new --index "$index" --output result.npz
cat extract.log
python - <<'PY'
import json, os, pathlib, socket
import numpy as np
with np.load('result.npz') as f: data={k:f[k] for k in f.files}
data['performance_json']=json.dumps({p.stem:p.read_text().strip() for p in pathlib.Path('.').glob('*.time')})
data['host']=socket.gethostname()
data['paired_order']=os.environ['INTEGRATION_PAIRED_ORDER']
data['root_bytes_json']=json.dumps({p.name:p.stat().st_size for p in pathlib.Path('.').glob('*.root')})
data['effective_reco_json']=pathlib.Path('effective_reco.json').read_text()
data['integration_provenance_json']=pathlib.Path('code/software_provenance.json').read_text()
np.savez_compressed('result.npz',**data)
PY
stage upload xrdcp --silent --force result.npz "$endpoint/$result"
python - <<'AUDIT'
import pathlib,tarfile
with tarfile.open('diagnostics.tar.gz','w:gz') as out:
    for path in pathlib.Path('.').glob('CKF*.jsonl'): out.add(path,arcname=path.name)
    for name in ['effective_reco.json','reco.time','momentum_quality.jsonl.gz']:
        out.add(name,arcname=name)
AUDIT
stage audit_upload xrdcp --silent --force diagnostics.tar.gz "$endpoint/${result%.npz}.tar.gz"
)
echo "completed master integration index=$index skip=$skip"
