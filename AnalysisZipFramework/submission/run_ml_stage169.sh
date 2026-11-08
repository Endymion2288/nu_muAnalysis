#!/usr/bin/env bash
set -eo pipefail
stage169_phase=$1
stage169_script=${stage169_phase%_retry}
stage169_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage169.XXXXXX")
tar -xzf energy-ml-stage169.tar.gz -C "$stage169_work"
cd "$stage169_work"
mkdir -p workbook/stage169_energy_ml ntuples/energy_ml_stage169
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage169_start
stage169_status=0
(
 /usr/bin/time -v -o "workbook/stage169_energy_ml/${stage169_phase}_time.txt" python3 -u "ml/stage169_${stage169_script}.py" > "workbook/stage169_energy_ml/${stage169_phase}.log" 2>&1 || exit $?
) || stage169_status=$?
printf '%s\n' "$stage169_status" > "workbook/stage169_energy_ml/${stage169_phase}_exitcode.txt"
find workbook/stage169_energy_ml ntuples/energy_ml_stage169 -type f -newer .stage169_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage169/${stage169_phase}_result.tar.gz"
exit "$stage169_status"
