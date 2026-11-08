#!/usr/bin/env bash
set -eo pipefail
stage162_phase=$1
stage162_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage162.XXXXXX")
tar -xzf energy-ml-stage162.tar.gz -C "$stage162_work"
cd "$stage162_work"
mkdir -p workbook/stage162_energy_ml ntuples/energy_ml_stage162 ScintIdDictFiles
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
touch .stage162_start
stage162_status=0
if [[ "$stage162_phase" == producer_audit ]]; then
    /usr/bin/time -v -o workbook/stage162_energy_ml/producer_audit_time.txt python3 -u ml/stage162_producer_audit.py || stage162_status=$?
elif [[ "$stage162_phase" == content_audit ]]; then
    /usr/bin/time -v -o workbook/stage162_energy_ml/content_audit_time.txt python3 -u ml/stage162_content_audit.py || stage162_status=$?
else
(
    export NU_MU_SKIP_LCG=1
    source setup_env.sh || exit $?
    nu_mu_official_setup "$stage162_work/runtime" || exit $?
    cp workbook/stage161_energy_ml/IdDictScintillator_2024.xml ScintIdDictFiles/IdDictScintillator.xml
    cmp workbook/stage161_energy_ml/IdDictScintillator_2024.xml ScintIdDictFiles/IdDictScintillator.xml || exit $?
    export XMLPATH="$stage162_work:${XMLPATH:-}"
    export DATAPATH="$stage162_work:${DATAPATH:-}"
    /usr/bin/time -v -o "workbook/stage162_energy_ml/${stage162_phase}_raw_time.txt" python -u ml/stage162_raw.py "$stage162_phase" > "workbook/stage162_energy_ml/${stage162_phase}_raw.log" 2>&1 || exit $?
    /usr/bin/time -v -o "workbook/stage162_energy_ml/${stage162_phase}_native_time.txt" python -u ml/stage162_native.py "$stage162_phase" > "workbook/stage162_energy_ml/${stage162_phase}_native.log" 2>&1
) || stage162_status=$?
if [[ "$stage162_status" == 0 ]]; then
    (
        source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh || exit $?
        /usr/bin/time -v -o "workbook/stage162_energy_ml/${stage162_phase}_comparison_time.txt" python -u ml/stage162_compare.py "$stage162_phase"
    ) || stage162_status=$?
fi
fi
printf '%s\n' "$stage162_status" > "workbook/stage162_energy_ml/${stage162_phase}_exitcode.txt"
find workbook/stage162_energy_ml ntuples/energy_ml_stage162 -type f -newer .stage162_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage162/${stage162_phase}_result.tar.gz"
exit "$stage162_status"
