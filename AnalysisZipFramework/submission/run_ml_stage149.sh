#!/usr/bin/env bash
set -eo pipefail
stage149_phase=$1
stage149_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage149.XXXXXX")
tar -xzf energy-ml-stage149.tar.gz -C "$stage149_work"
cd "$stage149_work"
mkdir -p workbook/stage149_energy_ml ntuples/energy_ml_stage149
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage149_start
stage149_status=0
if [[ "$stage149_phase" == audit || "$stage149_phase" == admission ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o "workbook/stage149_energy_ml/${stage149_phase}_time.txt" python -u ml/stage149_audit.py || stage149_status=$?
else
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage149_work/runtime"
    stage149_pipeline_phase=$stage149_phase
    if [[ "$stage149_phase" == pilot_retry ]]; then stage149_pipeline_phase=pilot; fi
    if [[ "$stage149_phase" == full_retry ]]; then stage149_pipeline_phase=full; fi
    /usr/bin/time -v -o "workbook/stage149_energy_ml/${stage149_phase}_time.txt" python -u ml/stage149_pipeline.py "$stage149_pipeline_phase" || stage149_status=$?
fi
printf '%s\n' "$stage149_status" > "workbook/stage149_energy_ml/${stage149_phase}_exitcode.txt"
find workbook/stage149_energy_ml ntuples/energy_ml_stage149 -type f -newer .stage149_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage149/${stage149_phase}_result.tar.gz"
exit "$stage149_status"
