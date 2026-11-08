#!/usr/bin/env bash
set -eo pipefail
stage195_phase=$1
stage195_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage195.XXXXXX")
tar -xzf energy-ml-stage195.tar.gz -C "$stage195_work"
cd "$stage195_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p workbook/stage195_energy_ml ntuples/energy_ml_stage195
touch .stage195_start
stage195_script=stage195_measure.py
if [[ "$stage195_phase" == audit* ]]; then stage195_script=stage195_audit.py; fi
stage195_status=0
/usr/bin/time -v -o "workbook/stage195_energy_ml/${stage195_phase}_time.txt" python -u "ml/${stage195_script}" "$stage195_phase" > "workbook/stage195_energy_ml/${stage195_phase}.log" 2>&1 || stage195_status=$?
printf '%s\n' "$stage195_status" > "workbook/stage195_energy_ml/${stage195_phase}_exitcode.txt"
find workbook/stage195_energy_ml ntuples/energy_ml_stage195 -type f -newer .stage195_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage195/${stage195_phase}_result.tar.gz"
exit "$stage195_status"
