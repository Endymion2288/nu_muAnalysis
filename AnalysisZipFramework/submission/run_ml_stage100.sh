#!/usr/bin/env bash
set -eo pipefail
stage100_mode=$1
case "$stage100_mode" in qa|fit|validate|audit) ;; *) exit 2 ;; esac
stage100_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage100.XXXXXX")
trap 'rm -rf "$stage100_scratch"' EXIT
tar -xzf energy-ml-stage100-$stage100_mode.tar.gz -C "$stage100_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
cd "$stage100_scratch"
stage100_status=0
/usr/bin/time -v -o workbook/stage100_energy_ml/time_$stage100_mode.txt timeout --signal=TERM --kill-after=5 180 python -u ml/stage100_$stage100_mode.py || stage100_status=$?
stage100_outputs=(workbook/stage100_energy_ml)
[[ ! -d ntuples/energy_ml_stage100 ]] || stage100_outputs+=(ntuples/energy_ml_stage100)
[[ ! -d ml/artifacts/stage100 ]] || stage100_outputs+=(ml/artifacts/stage100)
tar -czf result.tar.gz "${stage100_outputs[@]}"
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage100/result_$stage100_mode.tar.gz
exit "$stage100_status"
