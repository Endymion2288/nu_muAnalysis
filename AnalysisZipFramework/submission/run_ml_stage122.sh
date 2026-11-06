#!/usr/bin/env bash
set -eo pipefail
stage122_source=$1
stage122_phase=${2:-replicas}
stage122_limit=1750
if [[ "$stage122_phase" == replicas ]]; then stage122_limit=3500; fi
stage122_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage122.XXXXXX")
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
tar -xzf "energy-ml-stage122-${stage122_phase}.tar.gz" -C "$stage122_scratch"
export NU_MU_SKIP_LCG=1
source "$stage122_scratch/setup_env.sh"
nu_mu_official_setup "$stage122_scratch/runtime"
cd "$stage122_scratch"
mkdir -p ntuples/energy_ml_stage122 workbook/stage122_energy_ml
stage122_status=0
/usr/bin/time -v -o "workbook/stage122_energy_ml/${stage122_phase}_${stage122_source}_time.txt" timeout --signal=TERM --kill-after=10 "$stage122_limit" python -u ml/stage122_native.py --source "$stage122_source" --contract "workbook/stage122_energy_ml/${stage122_phase}_contract.json" --output "ntuples/energy_ml_stage122/${stage122_phase}_${stage122_source}.json.gz" || stage122_status=$?
tar -czf result.tar.gz workbook/stage122_energy_ml/*time.txt ntuples/energy_ml_stage122
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage122/${stage122_phase}_${stage122_source}_result.tar.gz"
exit "$stage122_status"
