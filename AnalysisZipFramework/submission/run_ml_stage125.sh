#!/usr/bin/env bash
set -eo pipefail
stage125_index=$1
stage125_phase=$2
stage125_limit=-1
if [[ "$stage125_phase" == pilot ]]; then stage125_limit=40; fi
stage125_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage125.XXXXXX")
trap 'rm -rf "$stage125_work"' EXIT
mkdir -p "$stage125_work/code" "$stage125_work/result"
tar -xzf energy-ml-stage125.tar.gz -C "$stage125_work/code"
cd "$stage125_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
stage125_kind=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["sources"][int(sys.argv[2])]["kind"])' code/workbook/stage125_energy_ml/protocol.json "$stage125_index")
stage125_pipeline() {
    if [[ "$stage125_kind" == rdo ]]; then
        bash -c 'source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh; python "$1/ml/stage125_request.py" "$1" "$2" "$3"' bash "$stage125_work/code" "$stage125_index" "$stage125_limit" > result/parent_log.txt 2>&1 || return
    fi
    export NU_MU_SKIP_LCG=1
    source code/setup_env.sh
    nu_mu_official_setup "$stage125_work/runtime" || return
    if [[ "$stage125_kind" == hits ]]; then
        /usr/bin/time -v -o result/parent_time.txt python code/ml/stage125_hits_request.py "$stage125_work/code" "$stage125_index" "$stage125_limit" > result/parent_log.txt 2>&1 || return
    fi
    stage125_run=$(python3 -c 'import json;print(json.load(open("request.json"))["source"]["run"])')
    stage125_input=$(python3 -c 'import json;d=json.load(open("request.json"))["source"];print(d.get("rdo",d["input"]))')
    python code/ml/stage119_payload.py --run "$stage125_run" --output result/payload.json || return
    if [[ "$stage125_kind" == hits ]]; then
        ln -s "$stage125_input" input-HITS.root
        # Full parent stream: sparse digitization changes the random/noise stream.
        /usr/bin/time -v -o result/digi_time.txt faser_digi.py --geom TI12MC04 --nevts "$stage125_limit" input-HITS.root > digi.log 2>&1 || return
    else
        ln -s "$stage125_input" input-RDO.root
    fi
    stage125_entries=$(python3 -c 'import json;print(len(json.load(open("request.json"))["entries"]))')
    if [[ "$stage125_entries" == 0 ]]; then printf '0\n' > result/empty.txt; return; fi
    /usr/bin/time -v -o result/reco_time.txt python code/ml/stage119_sparse_reco.py request.json > reco.log 2>&1 || return
    /usr/bin/time -v -o result/ntuple_time.txt faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType merge --nevents -1 --outfile ntuple.root input-xAOD.root > ntuple.log 2>&1 || return
    env -i PATH=/usr/bin:/bin HOME="$HOME" USER="$USER" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 bash -c '
        source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
        /usr/bin/time -v -o result/extract_time.txt python "$1/ml/stage125_extract.py" "$1" "$2"
    ' bash "$stage125_work/code" "$stage125_index" > result/extract_log.txt 2>&1 || return
}
stage125_status=0
stage125_pipeline || stage125_status=$?
printf '%s\n' "$stage125_status" > result/exitcode.txt
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
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage125/${stage125_phase}_${stage125_index}.tar.gz"
exit "$stage125_status"
