#!/usr/bin/env bash
set -eo pipefail
stage171_phase=$1
stage171_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage171.XXXXXX")
tar -xzf energy-ml-stage171.tar.gz -C "$stage171_work"
cd "$stage171_work"
mkdir -p workbook/stage171_energy_ml ntuples/energy_ml_stage171
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage171_start
stage171_status=0
(
 if [[ $stage171_phase != audit_finish ]]; then
 tar -xzf software/stage170/official_headers.tar.gz
 /usr/bin/time -v -o "workbook/stage171_energy_ml/${stage171_phase}_compile_time.txt" /usr/bin/g++ -std=c++17 -O2 -I headers ml/stage170_raw.cxx -lzstd -lz -llz4 -o reader > "workbook/stage171_energy_ml/${stage171_phase}_compile.log" 2>&1 || exit $?
 fi
 source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
 if [[ $stage171_phase == audit_finish ]]; then
  /usr/bin/time -v -o "workbook/stage171_energy_ml/${stage171_phase}_time.txt" python -u ml/stage171_finish.py > "workbook/stage171_energy_ml/${stage171_phase}.log" 2>&1 || exit $?
 else
 /usr/bin/time -v -o "workbook/stage171_energy_ml/${stage171_phase}_time.txt" python -u ml/stage171_run.py "$stage171_phase" > "workbook/stage171_energy_ml/${stage171_phase}.log" 2>&1 || exit $?
 fi
) || stage171_status=$?
printf '%s\n' "$stage171_status" > "workbook/stage171_energy_ml/${stage171_phase}_exitcode.txt"
find workbook/stage171_energy_ml ntuples/energy_ml_stage171 -type f -newer .stage171_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage171/${stage171_phase}_result.tar.gz"
exit "$stage171_status"
