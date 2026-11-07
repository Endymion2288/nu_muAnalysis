#!/usr/bin/env bash
set -eo pipefail
stage151_phase=$1
stage151_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage151.XXXXXX")
tar -xzf energy-ml-stage151.tar.gz -C "$stage151_work"
cd "$stage151_work"
mkdir -p workbook/stage151_energy_ml ntuples/energy_ml_stage151
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage151_start
stage151_status=0
if [[ "$stage151_phase" == audit || "$stage151_phase" == audit_detail || "$stage151_phase" == admission ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o "workbook/stage151_energy_ml/${stage151_phase}_time.txt" python -u ml/stage151_audit.py || stage151_status=$?
else
    export NU_MU_SKIP_LCG=1 NU_MU_NATIVE_CONTROL_STAGE=151 NU_MU_CONTROL_CONDITIONS=OFLCOND-FASER-04
    source setup_env.sh
    nu_mu_official_setup "$stage151_work/runtime"
    /usr/bin/time -v -o "workbook/stage151_energy_ml/${stage151_phase}_time.txt" python -u ml/stage149_pipeline.py "$stage151_phase" || stage151_status=$?
fi
printf '%s\n' "$stage151_status" > "workbook/stage151_energy_ml/${stage151_phase}_exitcode.txt"
find workbook/stage151_energy_ml ntuples/energy_ml_stage151 -type f -newer .stage151_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage151/${stage151_phase}_result.tar.gz"
exit "$stage151_status"
