#!/usr/bin/env bash
set -eo pipefail
latent_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_latent86.XXXXXX")
trap 'rm -rf "$latent_scratch"' EXIT
tar -xzf energy-ml-latent-stage86.tar.gz -C "$latent_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
ulimit -S -t 1080
ulimit -H -t 1100
latent_status=0
/usr/bin/time -v -o "$latent_scratch/workbook/stage86_energy_ml/worker.time" \
    timeout --signal=TERM --kill-after=10 1100 python -u "$latent_scratch/ml/latent_transfer_diagnostics.py" diagnose || latent_status=$?
tar -czf "$latent_scratch/results.tar.gz" -C "$latent_scratch" workbook/stage86_energy_ml
xrdcp --silent "$latent_scratch/results.tar.gz" "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage86/result.tar.gz"
exit "$latent_status"
