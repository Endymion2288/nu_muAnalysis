#!/usr/bin/env bash
set -eo pipefail
stage99_mode=$1
case "$stage99_mode" in qa|nativeqa|report|bqa|breport|bfinish|validate) ;; *) exit 2 ;; esac
stage99_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage99.XXXXXX")
trap 'rm -rf "$stage99_scratch"' EXIT
tar -xzf energy-ml-stage99-$stage99_mode.tar.gz -C "$stage99_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
cd "$stage99_scratch"
stage99_status=0
/usr/bin/time -v -o workbook/stage99_energy_ml/time_$stage99_mode.txt timeout --signal=TERM --kill-after=10 1700 python -u ml/stage99_$stage99_mode.py || stage99_status=$?
stage99_outputs=(workbook/stage99_energy_ml)
[[ ! -d ntuples/energy_ml_stage99 ]] || stage99_outputs+=(ntuples/energy_ml_stage99)
[[ ! -d ml/artifacts/stage99 ]] || stage99_outputs+=(ml/artifacts/stage99)
tar -czf result.tar.gz "${stage99_outputs[@]}"
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage99/result_$stage99_mode.tar.gz
exit "$stage99_status"
