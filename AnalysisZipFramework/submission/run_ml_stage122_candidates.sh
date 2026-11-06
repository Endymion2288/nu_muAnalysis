#!/usr/bin/env bash
set -eo pipefail
stage122_index=$1
stage122_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage122candidate.XXXXXX")
mkdir -p "$stage122_work/code" "$stage122_work/result"
tar -xzf energy-ml-stage122-candidates.tar.gz -C "$stage122_work/code"
python3 - "$stage122_work/code/workbook/stage122_energy_ml/replica_contract.json" "$stage122_index" "$stage122_work/request.json" <<'PY'
import json,sys
s=json.load(open(sys.argv[1]))['sources'][int(sys.argv[2])]
json.dump(dict(parent_N=s['parent_N'],entries=[c['entry'] for c in s['cases']],rdo='input-RDO.root',original_rdo=s['rdo'],run=s['run']),open(sys.argv[3],'w'))
PY
stage122_rdo=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["original_rdo"])' "$stage122_work/request.json")
stage122_run=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["run"])' "$stage122_work/request.json")
export NU_MU_SKIP_LCG=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source "$stage122_work/code/setup_env.sh"
nu_mu_official_setup "$stage122_work/runtime"
cd "$stage122_work"
ln -s "$stage122_rdo" input-RDO.root
stage122_status=0
stage122_pipeline() {
    python code/ml/stage119_payload.py --run "$stage122_run" --output result/payload.json || return
    /usr/bin/time -v -o result/reco_time.txt timeout --signal=TERM --kill-after=10 1750 python code/ml/stage119_sparse_reco.py request.json > result/reco_log.txt 2>&1 || return
    /usr/bin/time -v -o result/ntuple_time.txt timeout --signal=TERM --kill-after=10 900 faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType merge --nevents -1 --outfile ntuple.root input-xAOD.root > result/ntuple_log.txt 2>&1 || return
    env -i PATH=/usr/bin:/bin HOME="$HOME" USER="$USER" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 bash -c '
        source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
        /usr/bin/time -v -o "$4/extract_time.txt" python "$1/ml/stage122_replica_extract.py" "$2" "$3" "$4"
    ' bash "$stage122_work/code" "$stage122_index" "$stage122_work/ntuple.root" "$stage122_work/result" > result/extract_log.txt 2>&1 || return
}
stage122_pipeline || stage122_status=$?
printf '%s\n' "$stage122_status" > result/exitcode.txt
tar -czf result.tar.gz result
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage122/candidates_${stage122_index}_result.tar.gz"
exit "$stage122_status"
