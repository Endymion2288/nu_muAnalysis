#!/usr/bin/env bash
set -eo pipefail
stage173_phase=$1
stage173_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage173.XXXXXX")
tar -xzf energy-ml-stage173.tar.gz -C "$stage173_work"
cd "$stage173_work"
mkdir -p workbook/stage173_energy_ml ntuples/energy_ml_stage173
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage173_start
stage173_status=0
(
 export NU_MU_SKIP_LCG=1
 source setup_env.sh || exit $?
 nu_mu_official_setup "$stage173_work/runtime" || exit $?
 /usr/bin/time -v -o "workbook/stage173_energy_ml/${stage173_phase}_time.txt" python -u "ml/stage173_${stage173_phase}.py" > "workbook/stage173_energy_ml/${stage173_phase}.log" 2>&1 || exit $?
) || stage173_status=$?
printf '%s\n' "$stage173_status" > "workbook/stage173_energy_ml/${stage173_phase}_exitcode.txt"
find workbook/stage173_energy_ml ntuples/energy_ml_stage173 -type f -newer .stage173_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage173/${stage173_phase}_result.tar.gz"
exit "$stage173_status"
