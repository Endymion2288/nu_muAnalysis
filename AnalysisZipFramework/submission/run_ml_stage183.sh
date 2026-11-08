#!/usr/bin/env bash
set -eo pipefail
stage183_phase=$1
stage183_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage183.XXXXXX")
tar -xzf energy-ml-stage183.tar.gz -C "$stage183_work"
cd "$stage183_work"
mkdir -p workbook/stage183_energy_ml ntuples/energy_ml_stage183
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage183_start
stage183_status=0
(
 tar -xzf software/stage170/official_headers.tar.gz
 /usr/bin/time -v -o "workbook/stage183_energy_ml/${stage183_phase}_compile_time.txt" /usr/bin/g++ -std=c++17 -O2 -I headers ml/stage183_raw.cxx -lzstd -lz -llz4 -o reader > "workbook/stage183_energy_ml/${stage183_phase}_compile.log" 2>&1 || exit $?
 source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
 /usr/bin/time -v -o "workbook/stage183_energy_ml/${stage183_phase}_time.txt" python -u ml/stage183_measure.py "$stage183_phase" > "workbook/stage183_energy_ml/${stage183_phase}.log" 2>&1 || exit $?
) || stage183_status=$?
printf '%s\n' "$stage183_status" > "workbook/stage183_energy_ml/${stage183_phase}_exitcode.txt"
find workbook/stage183_energy_ml ntuples/energy_ml_stage183 -type f -newer .stage183_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage183/${stage183_phase}_result.tar.gz"
exit "$stage183_status"
