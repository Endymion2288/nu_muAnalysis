#!/usr/bin/env bash
set -eo pipefail
stage164_phase=$1
stage164_script=${stage164_phase%_retry}
stage164_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage164.XXXXXX")
tar -xzf energy-ml-stage164.tar.gz -C "$stage164_work"
cd "$stage164_work"
mkdir -p workbook/stage164_energy_ml ntuples/energy_ml_stage164
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage164_start
stage164_status=0
(
 source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
 /usr/bin/time -v -o "workbook/stage164_energy_ml/${stage164_phase}_time.txt" python -u "ml/stage164_${stage164_script}.py" > "workbook/stage164_energy_ml/${stage164_phase}.log" 2>&1 || exit $?
 if [[ "$stage164_phase" == analysis ]]; then python -u ml/stage164_plot.py; fi
) || stage164_status=$?
printf '%s\n' "$stage164_status" > "workbook/stage164_energy_ml/${stage164_phase}_exitcode.txt"
find workbook/stage164_energy_ml ntuples/energy_ml_stage164 ml/artifacts/stage164 -type f -newer .stage164_start -print0 2>/dev/null | tar --null -czf result.tar.gz -T - || true
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage164/${stage164_phase}_result.tar.gz"
exit "$stage164_status"
