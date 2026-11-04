#!/usr/bin/env bash
set -eo pipefail
batch_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_batch91.XXXXXX")
trap 'rm -rf "$batch_scratch"' EXIT
tar -xzf energy-ml-batched-stage91.tar.gz -C "$batch_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
ulimit -S -t 1500
ulimit -H -t 1520
batch_status=0
/usr/bin/time -v -o "$batch_scratch/workbook/stage91_energy_ml/job.time" \
    timeout --signal=TERM --kill-after=10 1700 python -u "$batch_scratch/ml/audit_batched_posterior.py" worker || batch_status=$?
batch_items=(workbook/stage91_energy_ml)
for batch_device in cpu cuda; do
    for batch_size in 256 1024; do
        batch_prediction="ntuples/energy_ml_stage91/${batch_device}_${batch_size}.npz"
        if [[ -f "$batch_scratch/$batch_prediction" ]]; then batch_items+=("$batch_prediction"); fi
    done
done
tar -czf "$batch_scratch/result.tar.gz" -C "$batch_scratch" "${batch_items[@]}"
xrdcp --silent "$batch_scratch/result.tar.gz" root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage91/result.tar.gz
exit "$batch_status"
