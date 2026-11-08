#!/usr/bin/env bash
set -eo pipefail
stage155_phase=$1
stage155_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage155.XXXXXX")
tar -xzf energy-ml-stage155.tar.gz -C "$stage155_work"
cd "$stage155_work"
mkdir -p workbook/stage155_energy_ml ntuples/energy_ml_stage155
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage155_start
stage155_status=0
if [[ "$stage155_phase" == audit || "$stage155_phase" == admission ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o "workbook/stage155_energy_ml/${stage155_phase}_time.txt" python -u ml/stage155_audit.py || stage155_status=$?
else
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage155_work/runtime"
    /usr/bin/time -v -o "workbook/stage155_energy_ml/${stage155_phase}_time.txt" python -u ml/stage155_native.py "$stage155_phase" || stage155_status=$?
fi
printf '%s\n' "$stage155_status" > "workbook/stage155_energy_ml/${stage155_phase}_exitcode.txt"
find workbook/stage155_energy_ml ntuples/energy_ml_stage155 -type f -newer .stage155_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage155/${stage155_phase}_result.tar.gz"
exit "$stage155_status"
