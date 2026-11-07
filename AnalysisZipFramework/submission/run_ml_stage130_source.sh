#!/usr/bin/env bash
set -eo pipefail
stage130_index=$1
stage130_phase=$2
stage130_limit=-1
if [[ "$stage130_phase" == pilot ]]; then stage130_limit=40; fi
stage130_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage130.XXXXXX")
trap 'rm -rf "$stage130_work"' EXIT
mkdir -p "$stage130_work/code" "$stage130_work/result"
tar -xzf "$NU_MU_STAGE130_PACKAGE" -C "$stage130_work/code"
cd "$stage130_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
stage130_kind=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["sources"][int(sys.argv[2])].get("kind","rdo"))' code/workbook/stage130_energy_ml/source_protocol.json "$stage130_index")
stage130_pipeline() {
    if [[ "$stage130_kind" == rdo ]]; then
        bash -c 'source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh; python "$1/ml/stage130_request.py" "$1" "$2" "$3"' bash "$stage130_work/code" "$stage130_index" "$stage130_limit" > result/parent_log.txt 2>&1 || return
    fi
    export NU_MU_SKIP_LCG=1
    source code/setup_env.sh
    nu_mu_official_setup "${NU_MU_STAGE130_RUNTIME:-$stage130_work/runtime}" || return
    if [[ "$stage130_kind" == hits ]]; then
        /usr/bin/time -v -o result/parent_time.txt python code/ml/stage130_hits_request.py "$stage130_work/code" "$stage130_index" "$stage130_limit" > result/parent_log.txt 2>&1 || return
    fi
    stage130_run=$(python3 -c 'import json;print(json.load(open("request.json"))["source"]["run"])')
    stage130_input=$(python3 -c 'import json;d=json.load(open("request.json"))["source"];print(d.get("rdo",d["input"]))')
    cp code/workbook/stage130_energy_ml/payload_snapshot.json result/payload.json || return
    if [[ "$stage130_kind" == hits ]]; then
        ln -s "$stage130_input" input-HITS.root
        # Full parent stream: sparse digitization changes the random/noise stream.
        /usr/bin/time -v -o result/digi_time.txt faser_digi.py --geom TI12MC04 --nevts "$stage130_limit" input-HITS.root > digi.log 2>&1 || return
    else
        ln -s "$stage130_input" input-RDO.root
    fi
    stage130_entries=$(python3 -c 'import json;print(len(json.load(open("request.json"))["entries"]))')
    if [[ "$stage130_entries" == 0 ]]; then printf '0\n' > result/empty.txt; return; fi
    /usr/bin/time -v -o result/reco_time.txt python code/ml/stage119_sparse_reco.py request.json > reco.log 2>&1 || return
    /usr/bin/time -v -o result/ntuple_time.txt faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType merge --nevents -1 --outfile ntuple.root input-xAOD.root > ntuple.log 2>&1 || return
    env -i PATH=/usr/bin:/bin HOME="$HOME" USER="$USER" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 bash -c '
        source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
        /usr/bin/time -v -o result/extract_time.txt python "$1/ml/stage130_extract.py" "$1" "$2"
    ' bash "$stage130_work/code" "$stage130_index" > result/extract_log.txt 2>&1 || return
    if [[ "$stage130_phase" == production ]]; then
        /usr/bin/time -v -o result/parentmap_time.txt python code/ml/stage130_parentmap.py request.json result/selected.npz result/parentmap.json > result/parentmap_log.txt 2>&1 || return
    fi
}
stage130_status=0
stage130_pipeline || stage130_status=$?
printf '%s\n' "$stage130_status" > result/exitcode.txt
python3 - <<'PY'
from pathlib import Path
for name in ['parent','digi','reco','ntuple']:
    p=Path(name+'.log')
    if p.exists():
        lines=p.read_text(errors='replace').splitlines()
        chosen=[v for v in lines if any(k in v for k in ['ERROR','FATAL','WAVE-Calibration','OFLCOND','UseIFT','CKFTrackCollection'])]
        Path('result/'+name+'_excerpt.txt').write_text('\n'.join(chosen+lines[-15:])+'\n')
p=Path('result/parent_log.txt')
if p.exists():
    lines=p.read_text(errors='replace').splitlines();p.write_text('\n'.join(lines[-20:])+'\n')
PY
tar -czf result.tar.gz result
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage130/${stage130_phase}_${stage130_index}.tar.gz"
exit "$stage130_status"
