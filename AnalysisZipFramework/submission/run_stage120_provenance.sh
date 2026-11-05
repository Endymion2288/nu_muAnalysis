#!/usr/bin/env bash
set -eo pipefail
scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage120.XXXXXX")
trap 'rm -rf "$scratch"' EXIT
tar -xzf energy-ml-stage120-provenance.tar.gz -C "$scratch"
cd "$scratch"
mkdir -p workbook/stage120_energy_ml
python3 ml/stage120_provenance.py
tar -czf result.tar.gz workbook/stage120_energy_ml/provenance_audit.json
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage120/provenance_result.tar.gz
