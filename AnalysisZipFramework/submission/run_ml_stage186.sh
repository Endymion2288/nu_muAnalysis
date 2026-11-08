#!/usr/bin/env bash
set -eo pipefail
stage186_phase=$1
stage186_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage186.XXXXXX")
tar -xzf energy-ml-stage186.tar.gz -C "$stage186_work"
cd "$stage186_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 NU_MU_SKIP_LCG=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage186_energy_ml ntuples/energy_ml_stage186 ml/artifacts/stage186
touch .stage186_start
if [[ "$stage186_phase" == fit || "$stage186_phase" == fit_repair || "$stage186_phase" == audit ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
else
    source setup_env.sh
    nu_mu_official_setup "$stage186_work/runtime"
fi
stage186_status=0
stage186_program=driver
if [[ "$stage186_phase" == fit || "$stage186_phase" == audit || "$stage186_phase" == probe ]]; then stage186_program=$stage186_phase; fi
if [[ "$stage186_phase" == fit_repair ]]; then stage186_program=fit; fi
/usr/bin/time -v -o "workbook/stage186_energy_ml/${stage186_phase}_time.txt" python -u "ml/stage186_${stage186_program}.py" "$stage186_phase" > "workbook/stage186_energy_ml/${stage186_phase}.log" 2>&1 || stage186_status=$?
printf '%s\n' "$stage186_status" > "workbook/stage186_energy_ml/${stage186_phase}_exitcode.txt"
find workbook/stage186_energy_ml ntuples/energy_ml_stage186 ml/artifacts/stage186 -type f -newer .stage186_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage186/${stage186_phase}_result.tar.gz"
exit "$stage186_status"
