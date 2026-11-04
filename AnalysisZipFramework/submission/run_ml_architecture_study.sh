#!/usr/bin/env bash
set -eo pipefail
architecture_scratch=$(mktemp -d /tmp/nu_mu_stage94.XXXXXX)
trap 'rm -rf "$architecture_scratch"' EXIT
architecture_eos=/eos/user/x/xcheng/FASER/nu_muAnalysis
tar -xzf "$architecture_eos/software/energy-ml-architectures-stage94.tar.gz" -C "$architecture_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="$architecture_scratch/software/stage94_packages"
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
ulimit -S -t 17000
ulimit -H -t 17100
architecture_status=0
python "$architecture_scratch/ml/time_architecture_worker.py" "$architecture_scratch" || architecture_status=$?
tar -czf "$architecture_scratch/result.tar.gz" -C "$architecture_scratch" workbook/stage94_energy_ml ml/artifacts/stage94 ntuples/energy_ml_stage94
cp "$architecture_scratch/result.tar.gz" "$architecture_eos/ntuples/energy_ml_stage94/result_fit.tar.gz.tmp"
mv "$architecture_eos/ntuples/energy_ml_stage94/result_fit.tar.gz.tmp" "$architecture_eos/ntuples/energy_ml_stage94/result_fit.tar.gz"
exit "$architecture_status"
