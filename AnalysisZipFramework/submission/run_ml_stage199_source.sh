#!/usr/bin/env bash
set -eo pipefail
stage199_index=$1
stage199_phase=$2
stage199_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage199_source.XXXXXX")
trap 'rm -rf "$stage199_work"' EXIT
mkdir -p "$stage199_work/result"
cd "$stage199_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
stage199_mode=$(python3 - "$NU_MU_STAGE199_CODE" "$stage199_index" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])/'workbook/stage199_energy_ml/protocol.json'
print(json.loads(p.read_text())['sources'][int(sys.argv[2])]['mode'])
PY
)
stage199_pipeline() {
    if [[ "$stage199_mode" == reco ]]; then
        stage199_pilot=()
        if [[ "$stage199_phase" == pilot ]]; then stage199_pilot=(--pilot); fi
        bash -c 'source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh; /usr/bin/time -v -o result/request.time python "$1/ml/stage199_source.py" request "$2" "${@:3}"' bash "$NU_MU_STAGE199_CODE" "$stage199_index" "${stage199_pilot[@]}" > result/request.log 2>&1 || return
        stage199_rdo=$(python3 -c 'import json;print(json.load(open("request.json"))["source"]["rdo"])')
        ln -s "$stage199_rdo" input-RDO.root
        export NU_MU_SKIP_LCG=1
        source "$NU_MU_STAGE199_CODE/setup_env.sh"
        nu_mu_official_setup "$NU_MU_STAGE199_RUNTIME" || return
        /usr/bin/time -v -o result/reco.time python "$NU_MU_STAGE199_CODE/ml/stage119_sparse_reco.py" request.json > reco.log 2>&1 || return
        /usr/bin/time -v -o result/ntuple.time faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType merge --nevents -1 --outfile ntuple.root input-xAOD.root > ntuple.log 2>&1 || return
        stage199_phys="$stage199_work/ntuple.root"
    else
        stage199_phys=$(python3 - "$NU_MU_STAGE199_CODE" "$stage199_index" <<'PY'
import json,sys
from pathlib import Path
print(json.loads((Path(sys.argv[1])/'workbook/stage199_energy_ml/protocol.json').read_text())['sources'][int(sys.argv[2])]['local_phys'])
PY
)
    fi
    env -i PATH=/usr/bin:/bin HOME="$HOME" USER="$USER" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 bash -c '
        source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
        /usr/bin/time -v -o result/extract.time python "$1/ml/stage199_source.py" extract "$2" --input "$3" --output result
    ' bash "$NU_MU_STAGE199_CODE" "$stage199_index" "$stage199_phys" > result/extract.log 2>&1 || return
}
stage199_status=0
stage199_pipeline || stage199_status=$?
printf '%s\n' "$stage199_status" > result/exitcode.txt
for stage199_log in reco.log ntuple.log; do
    if [[ -f "$stage199_log" ]]; then gzip -c "$stage199_log" > "result/$stage199_log.gz"; fi
done
tar -czf result.tar.gz result
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage199/${stage199_phase}_${stage199_index}.tar.gz"
exit "$stage199_status"
