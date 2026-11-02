#!/bin/bash
# Official reconstruction stays in stage55_scratch; publish only verified scalar features.
set -eo pipefail
stage55_index="$1"
stage55_mode="${2:-extract}"
stage55_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_low_energy.XXXXXX")
trap 'rm -rf "$stage55_scratch"' EXIT
mkdir -p "$stage55_scratch/code"
tar -xzf energy-ml-low-energy-stage55.tar.gz -C "$stage55_scratch/code"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
readarray -t stage55_fields < <(python3 - "$stage55_scratch/code/ml/configs/low_energy_files.tsv" "$stage55_index" <<'PY'
import csv,sys
r=list(csv.DictReader(open(sys.argv[1]),delimiter='\t'))[int(sys.argv[2])]
print(r['input']); print(r['rdo'])
PY
)
stage55_phys="${stage55_fields[0]}"
if [[ -z "$stage55_phys" ]]; then
    export NU_MU_SKIP_LCG=1
    export FASER_OFFICIAL_ARCHIVE="$PWD/calypso-master-d32b0ff3-el9-gcc13.tar.gz"
    source "$stage55_scratch/code/setup_env.sh"
    nu_mu_official_setup "$stage55_scratch/runtime"
    cd "$stage55_scratch"
    /usr/bin/time -f 'copy_rdo wall_s=%e cpu_user_s=%U cpu_system_s=%S rss_KiB=%M' \
        cp "${stage55_fields[1]}" input-RDO.root
    stage55_nevents=-1
    if [[ "$stage55_mode" == pilot ]]; then stage55_nevents=100; fi
    /usr/bin/time -f 'reco wall_s=%e cpu_user_s=%U cpu_system_s=%S rss_KiB=%M' -o reco.time \
        faser_reco.py --isMC --geom TI12MC04 --nevents "$stage55_nevents" input-RDO.root > reco.log 2>&1 || { tail -80 reco.log; exit 1; }
    cat reco.time
    /usr/bin/time -f 'ntuple wall_s=%e cpu_user_s=%U cpu_system_s=%S rss_KiB=%M' -o ntuple.time \
        faser_ntuple_maker.py --isMC --geom TI12MC04 --CKFTrackType merge --nevents "$stage55_nevents" \
        --outfile "$stage55_scratch/ntuple.root" input-xAOD.root > ntuple.log 2>&1 || { tail -80 ntuple.log; exit 1; }
    cat ntuple.time
    python "$stage55_scratch/code/AnalysisZipFramework/submission/validate_merge_ntuple.py" --rdo input-RDO.root \
        --xaod input-xAOD.root --ntuple ntuple.root --nevents "$stage55_nevents" --logs reco.log ntuple.log
    stage55_phys="$stage55_scratch/ntuple.root"
fi
# A fresh environment avoids mixing the Athena/GCC13 and analysis/GCC15 libraries.
env -i PATH=/usr/bin:/bin HOME="$HOME" USER="$USER" \
    PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    bash -c 'source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -f "extract wall_s=%e cpu_user_s=%U cpu_system_s=%S rss_KiB=%M" python "$1/ml/extract_low_energy.py" --index "$2" --input "$3" --output "$4"' \
    bash "$stage55_scratch/code" "$stage55_index" "$stage55_phys" "$stage55_scratch/result.npz"
stage55_destination="root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage55/shards/${stage55_index}.npz"
if [[ "$stage55_mode" == pilot ]]; then stage55_destination="${stage55_destination%.npz}_pilot.npz"; fi
xrdcp --silent --force "$stage55_scratch/result.npz" "$stage55_destination"
