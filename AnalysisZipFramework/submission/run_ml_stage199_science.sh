#!/usr/bin/env bash
set -eo pipefail
stage199_phase=$1
stage199_package="${2:-/eos/user/x/xcheng/FASER/nu_muAnalysis/software/energy-ml-stage199-science.tar.gz}"
stage199_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage199_science.XXXXXX")
trap 'rm -rf "$stage199_work"' EXIT
tar -xzf "$stage199_package" -C "$stage199_work"
cd "$stage199_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export NU_MU_STAGE199_DATA_ROOT=/eos/user/x/xcheng/FASER/nu_muAnalysis
if [[ "$stage199_phase" == fit ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
else
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
fi
mkdir -p workbook/stage199_energy_ml ntuples/energy_ml_stage199
touch .stage199_start
stage199_status=0
"$stage199_work/runtime/bin/time" -v -o "workbook/stage199_energy_ml/${stage199_phase}.time" python -u "ml/stage199_${stage199_phase}.py" > "workbook/stage199_energy_ml/${stage199_phase}.log" 2>&1 || stage199_status=$?
printf '%s\n' "$stage199_status" > "workbook/stage199_energy_ml/${stage199_phase}_exitcode.txt"
printf 'phase=%s science_exit=%s\n' "$stage199_phase" "$stage199_status"
if [[ "$stage199_status" != 0 ]]; then tail -n 40 "workbook/stage199_energy_ml/${stage199_phase}.log"; fi
stage199_dirs=(workbook/stage199_energy_ml ntuples/energy_ml_stage199)
if [[ -d ml/artifacts/stage199 ]]; then stage199_dirs+=(ml/artifacts/stage199); fi
find "${stage199_dirs[@]}" -type f -newer .stage199_start -print0 | tar --null -czf result.tar.gz -T -
if [[ -n "${KUBERNETES_SERVICE_HOST:-}" ]]; then
    stage199_destination="$NU_MU_STAGE199_DATA_ROOT/ntuples/energy_ml_stage199/${stage199_phase}_result.tar.gz"
    cp result.tar.gz "${stage199_destination}.partial.${HOSTNAME}"
    mv "${stage199_destination}.partial.${HOSTNAME}" "$stage199_destination"
else
    xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage199/${stage199_phase}_result.tar.gz"
fi
exit "$stage199_status"
