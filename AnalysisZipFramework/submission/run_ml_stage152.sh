#!/usr/bin/env bash
set -eo pipefail
stage152_phase=$1
stage152_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage152.XXXXXX")
tar -xzf energy-ml-stage152.tar.gz -C "$stage152_work"
cd "$stage152_work"
mkdir -p workbook/stage152_energy_ml ntuples/energy_ml_stage152
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage152_start
stage152_status=0
if [[ "$stage152_phase" == audit || "$stage152_phase" == admission ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o "workbook/stage152_energy_ml/${stage152_phase}_time.txt" python -u ml/stage152_audit.py || stage152_status=$?
else
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage152_work/runtime"
    /usr/bin/time -v -o "workbook/stage152_energy_ml/${stage152_phase}_time.txt" python -u ml/stage152_native.py "$stage152_phase" || stage152_status=$?
fi
printf '%s\n' "$stage152_status" > "workbook/stage152_energy_ml/${stage152_phase}_exitcode.txt"
find workbook/stage152_energy_ml ntuples/energy_ml_stage152 -type f -newer .stage152_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage152/${stage152_phase}_result.tar.gz"
exit "$stage152_status"
