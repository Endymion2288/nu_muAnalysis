#!/usr/bin/env bash
set -eo pipefail
readout_batch="$1"
readout_repository="$2"
readout_payload="$PWD"
readout_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_readout85.XXXXXX")
trap 'rm -rf "$readout_scratch"' EXIT
tar -xzf energy-ml-tracker-readout-stage85.tar.gz -C "$readout_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NU_MU_SKIP_LCG=1
export FASER_OFFICIAL_ARCHIVE="$readout_payload/calypso-master-d32b0ff3-el9-gcc13.tar.gz"
source "$readout_scratch/setup_env.sh"
nu_mu_official_setup "$readout_scratch/runtime"
ulimit -t 4200
cd "$readout_scratch"
readout_arguments=(--sample sample.json --sources "$readout_batch" "$((readout_batch+6))" "$((readout_batch+12))"
    --xml "$readout_scratch/runtime/XML" --output result.json)
if [[ "${3:-}" == "qa" ]]; then readout_arguments+=(--qa); fi
timeout 7100s python ml/read_tracker_readout.py "${readout_arguments[@]}"
if [[ "${3:-}" != "qa" ]]; then
    xrdcp -f --silent result.json "root://eoshome-x.cern.ch/$readout_repository/ntuples/energy_ml_stage85/native_${readout_batch}.json"
fi
