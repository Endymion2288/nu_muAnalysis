#!/usr/bin/env bash
# Stage82: remove the old one-hour/aggregate CPU restriction for frozen K sources.
set -eo pipefail
k_index=$1
k_events=${2:--1}
k_origin=$PWD
k_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_k82.XXXXXX")
trap 'rm -rf "$k_scratch"' EXIT
mkdir -p "$k_scratch/code" "$k_scratch/result"
tar -xzf energy-ml-k-support-stage82.tar.gz -C "$k_scratch/code"
k_rdo=$(python3 - "$k_scratch/code/workbook/stage82_energy_ml/production_protocol.json" "$k_index" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))['sources'][int(sys.argv[2])]['input_rdo'])
PY
)
export NU_MU_SKIP_LCG=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export FASER_OFFICIAL_ARCHIVE="$k_origin/calypso-master-d32b0ff3-el9-gcc13.tar.gz"
source "$k_scratch/code/setup_env.sh"
nu_mu_official_setup "$k_scratch/runtime"
cd "$k_scratch"
k_status=0
k_pipeline() {
    if [[ "$k_events" == -1 ]]; then
        /usr/bin/time -v -o result/copy.time cp "$k_rdo" input-RDO.root || return
    else
        ln -s "$k_rdo" input-RDO.root
    fi
    /usr/bin/time -v -o result/reco.time faser_reco.py --isMC --geom TI12MC04 --nevents "$k_events" input-RDO.root > reco.log 2>&1 || return
    /usr/bin/time -v -o result/ntuple.time faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType merge --nevents -1 --outfile ntuple.root input-xAOD.root > ntuple.log 2>&1 || return
    python "$k_scratch/code/AnalysisZipFramework/submission/validate_merge_ntuple.py" --rdo input-RDO.root --xaod input-xAOD.root --ntuple ntuple.root --nevents "$k_events" --logs reco.log ntuple.log > result/production_validation.txt 2>&1 || return
    env -i PATH=/usr/bin:/bin HOME="$HOME" USER="$USER" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 bash -c '
        source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
        /usr/bin/time -v -o "$4/extract.time" python "$1/ml/extract_k_support.py" --index "$2" --input "$3" --output "$4/selected.npz"
        python "$1/ml/check_k_calibration.py" "$3" "$4/calibration.json"
    ' bash "$k_scratch/code" "$k_index" "$k_scratch/ntuple.root" "$k_scratch/result" > result/extract.log 2>&1 || return
}
k_pipeline || k_status=$?
printf '%s\n' "$k_status" > result/exitcode.txt
tail -80 reco.log > result/reco_tail.txt 2>/dev/null || true
tail -40 ntuple.log > result/ntuple_tail.txt 2>/dev/null || true
grep -E 'OFLCOND|FASERNU|WAVE-Calibration|CKFTrackCollectionMerge|UseIFT|TI12MC04' reco.log ntuple.log > result/conditions.txt || true
tar -czf result.tar.gz result
if [[ "$k_events" == -1 ]]; then
    xrdcp --silent result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage82/k_$k_index.tar.gz"
else
    cp result.tar.gz "$k_origin/qa_$k_index.tar.gz"
fi
exit "$k_status"
