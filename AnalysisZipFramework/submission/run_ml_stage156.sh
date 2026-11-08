#!/usr/bin/env bash
set -eo pipefail
stage156_phase=$1
stage156_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage156.XXXXXX")
tar -xzf energy-ml-stage156.tar.gz -C "$stage156_work"
cd "$stage156_work"
mkdir -p workbook/stage156_energy_ml ntuples/energy_ml_stage156
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage156_start
stage156_status=0
if [[ "$stage156_phase" == audit || "$stage156_phase" == admission || "$stage156_phase" == admission_retry ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o "workbook/stage156_energy_ml/${stage156_phase}_time.txt" python -u ml/stage156_audit.py || stage156_status=$?
else
    export NU_MU_SKIP_LCG=1 NU_MU_NATIVE_CONTROL_STAGE=156 NU_MU_CONTROL_CONDITIONS=OFLCOND-FASER-06
    source setup_env.sh
    nu_mu_official_setup "$stage156_work/runtime"
    /usr/bin/time -v -o "workbook/stage156_energy_ml/${stage156_phase}_time.txt" python -u ml/stage156_pipeline.py "$stage156_phase" || stage156_status=$?
fi
printf '%s\n' "$stage156_status" > "workbook/stage156_energy_ml/${stage156_phase}_exitcode.txt"
find workbook/stage156_energy_ml ntuples/energy_ml_stage156 -type f -newer .stage156_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage156/${stage156_phase}_result.tar.gz"
exit "$stage156_status"
