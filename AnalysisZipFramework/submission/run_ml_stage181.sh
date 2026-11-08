#!/usr/bin/env bash
set -eo pipefail
stage181_phase=$1
stage181_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage181.XXXXXX")
tar -xzf energy-ml-stage181.tar.gz -C "$stage181_work"
cd "$stage181_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p workbook/stage181_energy_ml ntuples/energy_ml_stage181
touch .stage181_start
stage181_status=0
/usr/bin/time -v -o "workbook/stage181_energy_ml/${stage181_phase}_time.txt" python -u ml/stage181_measure.py "$stage181_phase" > "workbook/stage181_energy_ml/${stage181_phase}.log" 2>&1 || stage181_status=$?
printf '%s\n' "$stage181_status" > "workbook/stage181_energy_ml/${stage181_phase}_exitcode.txt"
find workbook/stage181_energy_ml ntuples/energy_ml_stage181 -type f -newer .stage181_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage181/${stage181_phase}_result.tar.gz"
exit "$stage181_status"
