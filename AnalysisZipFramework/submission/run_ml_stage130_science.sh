#!/usr/bin/env bash
set -eo pipefail
stage130_phase=$1
stage130_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage130_science.XXXXXX")
trap 'rm -rf "$stage130_work"' EXIT
tar -xzf "energy-ml-stage130-${stage130_phase}.tar.gz" -C "$stage130_work"
cd "$stage130_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
if [[ "$stage130_phase" == parentlink || "$stage130_phase" == parentlinkpilot || "$stage130_phase" == parentmappilot ]]; then
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage130_work/runtime"
else
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
fi
mkdir -p workbook/stage130_energy_ml ntuples/energy_ml_stage130 ml/artifacts/stage130
touch .stage130_output_start
stage130_status=0
/usr/bin/time -v -o "workbook/stage130_energy_ml/${stage130_phase}_time.txt" python -u "ml/stage130_${stage130_phase}.py" || stage130_status=$?
printf '%s\n' "$stage130_status" > "workbook/stage130_energy_ml/${stage130_phase}_exitcode.txt"
find workbook/stage130_energy_ml ntuples/energy_ml_stage130 ml/artifacts/stage130 -type f -newer .stage130_output_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage130/${stage130_phase}_result.tar.gz"
exit "$stage130_status"
