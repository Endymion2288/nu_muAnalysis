#!/usr/bin/env bash
set -eo pipefail
candidate_mode=${1:-extract}
case "$candidate_mode" in
    extract|fit|report) ;;
    *) exit 2 ;;
esac
candidate_repo=/eos/user/x/xcheng/FASER/nu_muAnalysis
candidate_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage96.XXXXXX")
trap 'rm -rf "$candidate_scratch"' EXIT
candidate_package=energy-ml-candidates-stage96-$candidate_mode.tar.gz
if [[ "$candidate_mode" == fit ]]; then
    tar -xzf "$candidate_repo/software/$candidate_package" -C "$candidate_scratch"
else
    tar -xzf "$candidate_package" -C "$candidate_scratch"
fi
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
candidate_limit=1740
if [[ "$candidate_mode" == fit ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
    candidate_limit=7000
else
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
fi
candidate_status=0
timeout --signal=TERM --kill-after=10 "$candidate_limit" python -u "$candidate_scratch/ml/time_candidate_worker.py" "$candidate_scratch" "$candidate_mode" || candidate_status=$?
case "$candidate_mode" in
    extract) tar -czf "$candidate_scratch/result.tar.gz" -C "$candidate_scratch" workbook/stage96_energy_ml ntuples/energy_ml_stage96 ;;
    fit) tar -czf "$candidate_scratch/result.tar.gz" -C "$candidate_scratch" workbook/stage96_energy_ml ml/artifacts/stage96 ;;
    report) tar -czf "$candidate_scratch/result.tar.gz" -C "$candidate_scratch" workbook/stage96_energy_ml ;;
esac
if [[ "$candidate_mode" == fit ]]; then
    cp "$candidate_scratch/result.tar.gz" "$candidate_repo/ntuples/energy_ml_stage96/result_fit.tar.gz.tmp"
    mv "$candidate_repo/ntuples/energy_ml_stage96/result_fit.tar.gz.tmp" "$candidate_repo/ntuples/energy_ml_stage96/result_fit.tar.gz"
else
    xrdcp --force --silent "$candidate_scratch/result.tar.gz" "root://eoshome-x.cern.ch/$candidate_repo/ntuples/energy_ml_stage96/result_$candidate_mode.tar.gz"
fi
exit "$candidate_status"
