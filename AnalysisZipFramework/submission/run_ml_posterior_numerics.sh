#!/usr/bin/env bash
set -eo pipefail
numerics_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_numerics88.XXXXXX")
trap 'rm -rf "$numerics_scratch"' EXIT
tar -xzf energy-ml-numerics-stage88.tar.gz -C "$numerics_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
ulimit -S -t 1650
ulimit -H -t 1680
numerics_status=0
/usr/bin/time -v -o "$numerics_scratch/workbook/stage88_energy_ml/job.time" \
    timeout --signal=TERM --kill-after=10 1740 python -u "$numerics_scratch/ml/audit_posterior_integration.py" run || numerics_status=$?
tar -czf "$numerics_scratch/result.tar.gz" -C "$numerics_scratch" workbook/stage88_energy_ml
xrdcp --silent "$numerics_scratch/result.tar.gz" root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage88/result.tar.gz
exit "$numerics_status"
