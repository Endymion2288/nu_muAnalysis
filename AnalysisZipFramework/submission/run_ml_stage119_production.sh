#!/usr/bin/env bash
set -eo pipefail
stage119_index=$1
stage119_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage119prod.XXXXXX")
trap 'rm -rf "$stage119_work"' EXIT
mkdir -p "$stage119_work/code" "$stage119_work/result"
tar -xzf energy-ml-stage119-production.tar.gz -C "$stage119_work/code"
python3 - "$stage119_work/code/workbook/stage119_energy_ml/production_contract.json" "$stage119_index" "$stage119_work/request.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]))['requests'][int(sys.argv[2])];p['rdo_original']=p['rdo'];p['rdo']='input-RDO.root'
json.dump(p,open(sys.argv[3],'w'))
PY
stage119_rdo=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["rdo_original"])' "$stage119_work/request.json")
stage119_run=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["source"]["run"])' "$stage119_work/request.json")
export NU_MU_SKIP_LCG=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source "$stage119_work/code/setup_env.sh"
nu_mu_official_setup "$stage119_work/runtime"
cd "$stage119_work"
ln -s "$stage119_rdo" input-RDO.root
stage119_status=0
stage119_pipeline() {
    python code/ml/stage119_payload.py --run "$stage119_run" --output result/payload.json || return
    /usr/bin/time -v -o result/reco_time.txt python code/ml/stage119_sparse_reco.py request.json > reco.log 2>&1 || return
    /usr/bin/time -v -o result/ntuple_time.txt faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType merge --nevents -1 --outfile ntuple.root input-xAOD.root > ntuple.log 2>&1 || return
    env -i PATH=/usr/bin:/bin HOME="$HOME" USER="$USER" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 bash -c '
        source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
        /usr/bin/time -v -o "$4/extract_time.txt" python "$1/ml/stage119_production_extract.py" "$1" "$2" "$3" "$4"
    ' bash "$stage119_work/code" "$stage119_index" "$stage119_work/ntuple.root" "$stage119_work/result" > result/extract_log.txt 2>&1 || return
}
stage119_pipeline || stage119_status=$?
printf '%s\n' "$stage119_status" > result/exitcode.txt
python3 - <<'PY'
from pathlib import Path
for name in ['reco','ntuple']:
    path=Path(name+'.log')
    if path.exists():
        lines=path.read_text(errors='replace').splitlines()
        selected=[line for line in lines if any(k in line for k in ['ERROR','FATAL','WAVE-Calibration','OFLCOND','UseIFT','CKFTrackCollection'])]
        Path('result/'+name+'_excerpt.txt').write_text('\n'.join(selected+lines[-20:])+'\n')
PY
tar -czf result.tar.gz result
xrdcp --silent result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage119/production_${stage119_index}.tar.gz"
exit "$stage119_status"
