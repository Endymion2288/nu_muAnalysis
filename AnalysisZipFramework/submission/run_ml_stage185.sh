#!/usr/bin/env bash
set -eo pipefail
stage185_phase=$1
stage185_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage185.XXXXXX")
tar -xzf energy-ml-stage185.tar.gz -C "$stage185_work"
cd "$stage185_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 NU_MU_SKIP_LCG=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage185_energy_ml ntuples/energy_ml_stage185
touch .stage185_start
source setup_env.sh
nu_mu_official_setup "$stage185_work/runtime"
stage185_status=0
stage185_program=$stage185_phase
if [[ "$stage185_phase" == batch ]]; then stage185_program=native; fi
if [[ "$stage185_phase" == identity_repair || "$stage185_phase" == identity_fix ]]; then stage185_program=identity; fi
/usr/bin/time -v -o "workbook/stage185_energy_ml/${stage185_phase}_time.txt" python -u "ml/stage185_${stage185_program}.py" > "workbook/stage185_energy_ml/${stage185_phase}.log" 2>&1 || stage185_status=$?
printf '%s\n' "$stage185_status" > "workbook/stage185_energy_ml/${stage185_phase}_exitcode.txt"
find workbook/stage185_energy_ml ntuples/energy_ml_stage185 -type f -newer .stage185_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage185/${stage185_phase}_result.tar.gz"
exit "$stage185_status"
