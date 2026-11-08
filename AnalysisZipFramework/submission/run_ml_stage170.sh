#!/usr/bin/env bash
set -eo pipefail
stage170_phase=$1
stage170_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage170.XXXXXX")
tar -xzf energy-ml-stage170.tar.gz -C "$stage170_work"
cd "$stage170_work"
mkdir -p workbook/stage170_energy_ml ntuples/energy_ml_stage170
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage170_start
stage170_status=0
(
 tar -xzf software/stage170/official_headers.tar.gz
 /usr/bin/time -v -o "workbook/stage170_energy_ml/${stage170_phase}_compile_time.txt" /usr/bin/g++ -std=c++17 -O2 -I headers ml/stage170_raw.cxx -lzstd -lz -llz4 -o reader > "workbook/stage170_energy_ml/${stage170_phase}_compile.log" 2>&1 || exit $?
 source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
 /usr/bin/time -v -o "workbook/stage170_energy_ml/${stage170_phase}_time.txt" python -u ml/stage170_run.py "$stage170_phase" > "workbook/stage170_energy_ml/${stage170_phase}.log" 2>&1 || exit $?
) || stage170_status=$?
printf '%s\n' "$stage170_status" > "workbook/stage170_energy_ml/${stage170_phase}_exitcode.txt"
find workbook/stage170_energy_ml ntuples/energy_ml_stage170 -type f -newer .stage170_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage170/${stage170_phase}_result.tar.gz"
exit "$stage170_status"
