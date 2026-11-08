#!/usr/bin/env bash
set -eo pipefail
stage153_phase=$1
stage153_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage153.XXXXXX")
tar -xzf energy-ml-stage153.tar.gz -C "$stage153_work"
cd "$stage153_work"
mkdir -p workbook/stage153_energy_ml ntuples/energy_ml_stage153
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage153_start
stage153_status=0
if [[ "$stage153_phase" == audit ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o "workbook/stage153_energy_ml/${stage153_phase}_time.txt" python -u ml/stage153_audit.py || stage153_status=$?
else
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage153_work/runtime"
    /usr/bin/time -v -o "workbook/stage153_energy_ml/${stage153_phase}_time.txt" python -u ml/stage153_native.py || stage153_status=$?
fi
printf '%s\n' "$stage153_status" > "workbook/stage153_energy_ml/${stage153_phase}_exitcode.txt"
find workbook/stage153_energy_ml ntuples/energy_ml_stage153 -type f -newer .stage153_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage153/${stage153_phase}_result.tar.gz"
exit "$stage153_status"
