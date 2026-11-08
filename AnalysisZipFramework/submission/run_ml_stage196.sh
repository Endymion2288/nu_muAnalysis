#!/usr/bin/env bash
set -eo pipefail
stage196_phase=$1
stage196_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage196.XXXXXX")
tar -xzf energy-ml-stage196.tar.gz -C "$stage196_work"
cd "$stage196_work"
mkdir -p workbook/stage196_energy_ml ntuples/energy_ml_stage196
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage196_start
stage196_status=0
(
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage196_work/runtime"
    /usr/bin/time -v -o "workbook/stage196_energy_ml/${stage196_phase}_raw_time.txt" python -u ml/stage196_raw.py "$stage196_phase" > "workbook/stage196_energy_ml/${stage196_phase}_raw.log" 2>&1
) || stage196_status=$?
if [[ "$stage196_status" == 0 ]]; then
    (
        source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
        stage196_script=stage196_measure.py
        if [[ "$stage196_phase" == audit ]]; then stage196_script=stage196_audit.py; fi
        /usr/bin/time -v -o "workbook/stage196_energy_ml/${stage196_phase}_statistics_time.txt" python -u "ml/${stage196_script}" "$stage196_phase" > "workbook/stage196_energy_ml/${stage196_phase}_statistics.log" 2>&1
    ) || stage196_status=$?
fi
printf '%s\n' "$stage196_status" > "workbook/stage196_energy_ml/${stage196_phase}_exitcode.txt"
find workbook/stage196_energy_ml ntuples/energy_ml_stage196 -type f -newer .stage196_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage196/${stage196_phase}_result.tar.gz"
exit "$stage196_status"
