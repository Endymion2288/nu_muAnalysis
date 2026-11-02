#!/usr/bin/env bash
set -eo pipefail
batch="$1"
tracker_noise_arm="$2"
repository="$3"
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_tracker_noise.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
payload_dir="$PWD"
tar -xzf energy-ml-tracker-noise-stage53.tar.gz -C "$scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NU_MU_SKIP_LCG=1
export FASER_OFFICIAL_ARCHIVE="$payload_dir/calypso-master-d32b0ff3-el9-gcc13.tar.gz"
source "$scratch/setup_env.sh"
nu_mu_official_setup "$scratch/runtime"
python "$scratch/ml/build_tracker_noise_helper.py" --output "$scratch/tracks.so"
cd "$scratch"
python - "$batch" <<'PY'
import json,sys
from pathlib import Path
sample=json.load(open('sample.json'))
batch=int(sys.argv[1])
for source in [batch,batch+6]:
    row=sample['sources'][source]
    Path(f'cases_{source}.json').write_text(json.dumps(row['cases']))
    Path(f'entries_{source}.json').write_text(json.dumps([c['entry'] for c in row['cases']]))
PY
for offset in 0 6; do
    index=$((batch+offset))
    read -r run rdo < <(python - "$index" <<'PY'
import json,sys
row=json.load(open('sample.json'))['sources'][int(sys.argv[1])]
print(row['run'],row['input_rdo'])
PY
)
    /usr/bin/time -f 'stage53_replay wall_s=%e max_rss_KiB=%M user_s=%U system_s=%S' \
        timeout 900s python ml/replay_tracker_noise.py --input-rdo "$rdo" --run "$run" \
        --entries "entries_$index.json" --expected-cases "cases_$index.json" --mode "$tracker_noise_arm" \
        --original-hits --with-tracking --tracking-helper "$scratch/tracks.so" \
        --converter-header "$scratch/FaserSCT3_RawDataCnv_p4.h" --output "$scratch/${tracker_noise_arm}_$index.json"
    xrdcp -f --silent "$scratch/${tracker_noise_arm}_$index.json" "root://eoshome-x.cern.ch/$repository/ntuples/energy_ml_stage53/${tracker_noise_arm}_$index.json"
done
