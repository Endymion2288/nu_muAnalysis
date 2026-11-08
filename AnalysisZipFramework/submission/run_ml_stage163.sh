#!/usr/bin/env bash
set -eo pipefail
stage163_phase=$1
stage163_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage163.XXXXXX")
tar -xzf energy-ml-stage163.tar.gz -C "$stage163_work"
cd "$stage163_work"
mkdir -p workbook/stage163_energy_ml ntuples/energy_ml_stage163
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage163_start
stage163_status=0
(
 source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
 case "$stage163_phase" in
  pilot|repeat|batch_*) stage163_script=extract ;;
  admission*) stage163_script=admission ;;
  source_repair*) stage163_script=source_repair ;;
  fit|validate) stage163_script=$stage163_phase ;;
  *) exit 2 ;;
 esac
 /usr/bin/time -v -o "workbook/stage163_energy_ml/${stage163_phase}_time.txt" python -u "ml/stage163_${stage163_script}.py" "${stage163_phase%_repair}" > "workbook/stage163_energy_ml/${stage163_phase}.log" 2>&1
) || stage163_status=$?
printf '%s\n' "$stage163_status" > "workbook/stage163_energy_ml/${stage163_phase}_exitcode.txt"
find workbook/stage163_energy_ml ntuples/energy_ml_stage163 ml/artifacts/stage163 -type f -newer .stage163_start -print0 2>/dev/null | tar --null -czf result.tar.gz -T - || true
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage163/${stage163_phase}_result.tar.gz"
exit "$stage163_status"
