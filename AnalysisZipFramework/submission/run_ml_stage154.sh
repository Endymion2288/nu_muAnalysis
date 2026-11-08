#!/usr/bin/env bash
set -eo pipefail
stage154_phase=$1
stage154_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage154.XXXXXX")
tar -xzf energy-ml-stage154.tar.gz -C "$stage154_work"
cd "$stage154_work"
mkdir -p workbook/stage154_energy_ml ntuples/energy_ml_stage154
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage154_start
stage154_status=0
if [[ "$stage154_phase" == audit || "$stage154_phase" == admission ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o "workbook/stage154_energy_ml/${stage154_phase}_time.txt" python -u ml/stage154_audit.py || stage154_status=$?
else
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage154_work/runtime"
    /usr/bin/time -v -o "workbook/stage154_energy_ml/${stage154_phase}_time.txt" python -u ml/stage154_native.py "$stage154_phase" || stage154_status=$?
fi
printf '%s\n' "$stage154_status" > "workbook/stage154_energy_ml/${stage154_phase}_exitcode.txt"
find workbook/stage154_energy_ml ntuples/energy_ml_stage154 -type f -newer .stage154_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage154/${stage154_phase}_result.tar.gz"
exit "$stage154_status"
