#!/usr/bin/env bash
set -eo pipefail
retrain_kube_scratch=$(mktemp -d /tmp/nu_mu_retrain92_kube.XXXXXX)
trap 'rm -rf "$retrain_kube_scratch"' EXIT
retrain_eos=/eos/user/x/xcheng/FASER/nu_muAnalysis
tar -xzf "$retrain_eos/software/energy-ml-retrain-stage92-fit.tar.gz" -C "$retrain_kube_scratch"
mkdir -p "$retrain_kube_scratch/ml/artifacts/stage92" "$retrain_kube_scratch/workbook/stage92_energy_ml"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader > "$retrain_kube_scratch/workbook/stage92_energy_ml/kubeflow_gpu.txt"
python -c 'import torch; assert torch.__version__ == "2.10.0" and torch.cuda.is_available(); print("frozen torch/CUDA runtime verified")'
ulimit -S -t 7000
ulimit -H -t 7100
retrain_kube_status=0
python "$retrain_eos/ml/time_stage92_worker.py" "$retrain_kube_scratch/ml/retrain_accurate_posterior.py" || retrain_kube_status=$?
retrain_kube_items=(workbook/stage92_energy_ml ml/artifacts/stage92)
for retrain_kube_file in startup_heads.npz failed_numerics.npz; do
    if [[ -f "$retrain_kube_scratch/ntuples/energy_ml_stage92/$retrain_kube_file" ]]; then
        retrain_kube_items+=("ntuples/energy_ml_stage92/$retrain_kube_file")
    fi
done
tar -czf "$retrain_kube_scratch/result.tar.gz" -C "$retrain_kube_scratch" "${retrain_kube_items[@]}"
cp "$retrain_kube_scratch/result.tar.gz" "$retrain_eos/ntuples/energy_ml_stage92/result_fit_kubeflow.tar.gz.tmp"
mv "$retrain_eos/ntuples/energy_ml_stage92/result_fit_kubeflow.tar.gz.tmp" "$retrain_eos/ntuples/energy_ml_stage92/result_fit_kubeflow.tar.gz"
exit "$retrain_kube_status"
