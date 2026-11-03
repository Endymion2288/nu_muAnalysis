#!/usr/bin/env bash
# Immutable stage70 worker: full selected RDO, scratch reconstruction, scalar return.
set -eo pipefail
stage70_index=$1
stage70_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_support.XXXXXX")
trap 'rm -rf "$stage70_scratch"' EXIT
mkdir -p "$stage70_scratch/code" "$stage70_scratch/result"
tar -xzf energy-ml-alternative-support-stage70.tar.gz -C "$stage70_scratch/code"
stage70_rdo=$(python3 - "$stage70_scratch/code/ml/configs/alternative_support_pilot.json" "$stage70_index" <<'PY'
import json,sys
print(json.load(open(sys.argv[1]))['sources'][int(sys.argv[2])]['input_rdo'])
PY
)
export NU_MU_SKIP_LCG=1 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export FASER_OFFICIAL_ARCHIVE="$PWD/calypso-master-d32b0ff3-el9-gcc13.tar.gz"
source "$stage70_scratch/code/setup_env.sh"
nu_mu_official_setup "$stage70_scratch/runtime"
cd "$stage70_scratch"
stage70_status=0
stage70_pipeline() {
    /usr/bin/time -f 'copy wall_s=%e user_s=%U system_s=%S maxRSS_KiB=%M' -o result/copy.time cp "$stage70_rdo" input-RDO.root || return
    /usr/bin/time -f 'reco wall_s=%e user_s=%U system_s=%S maxRSS_KiB=%M' -o result/reco.time \
        faser_reco.py --isMC --geom TI12MC04 --nevents -1 input-RDO.root > reco.log 2>&1 || return
    /usr/bin/time -f 'ntuple wall_s=%e user_s=%U system_s=%S maxRSS_KiB=%M' -o result/ntuple.time \
        faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType merge --nevents -1 \
        --outfile ntuple.root input-xAOD.root > ntuple.log 2>&1 || return
    python "$stage70_scratch/code/AnalysisZipFramework/submission/validate_merge_ntuple.py" \
        --rdo input-RDO.root --xaod input-xAOD.root --ntuple ntuple.root --logs reco.log ntuple.log > result/production_validation.txt 2>&1 || return
    env -i PATH=/usr/bin:/bin HOME="$HOME" USER="$USER" PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
        OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 bash -c '
        source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
        /usr/bin/time -f "extract wall_s=%e user_s=%U system_s=%S maxRSS_KiB=%M" -o "$4/extract.time" \
        python "$1/ml/extract_alternative_support.py" --index "$2" --input "$3" --output "$4/selected.npz"
        ' bash "$stage70_scratch/code" "$stage70_index" "$stage70_scratch/ntuple.root" "$stage70_scratch/result" \
        > result/extract.log 2>&1 || return
}
stage70_pipeline || stage70_status=$?
printf '%s\n' "$stage70_status" > result/exitcode.txt
# Compact diagnostics only; full logs and all ROOT intermediates die with scratch.
tail -60 reco.log > result/reco_tail.txt 2>/dev/null || true
tail -20 ntuple.log > result/ntuple_tail.txt 2>/dev/null || true
tar -czf result.tar.gz result
xrdcp --silent result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage70/$stage70_index.tar.gz"
exit "$stage70_status"
