#!/usr/bin/env bash
set -eo pipefail
stage129_phase=$1
stage129_index=${2:-0}
stage129_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage129.XXXXXX")
tar -xzf "energy-ml-stage129-${stage129_phase}.tar.gz" -C "$stage129_work"
cd "$stage129_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage129_energy_ml ntuples/energy_ml_stage129 ml/artifacts/stage129
touch .stage129_output_start
stage129_status=0
if [[ "$stage129_phase" == pilot || "$stage129_phase" == pilot2 || "$stage129_phase" == extract || "$stage129_phase" == geometry || "$stage129_phase" == official || "$stage129_phase" == officialfull || "$stage129_phase" == evntprobe || "$stage129_phase" == genmeta || "$stage129_phase" == evntrange || "$stage129_phase" == trackcov || "$stage129_phase" == muanchor || "$stage129_phase" == timereplay || "$stage129_phase" == fullchain || "$stage129_phase" == fullchainpilot || "$stage129_phase" == fullchaincached || "$stage129_phase" == fullchainseed || "$stage129_phase" == fullchainrepeat ]]; then
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage129_work/runtime"
    if [[ "$stage129_phase" == pilot || "$stage129_phase" == pilot2 || "$stage129_phase" == extract ]]; then
        /usr/bin/time -v -o "workbook/stage129_energy_ml/${stage129_phase}_${stage129_index}_time.txt" timeout --signal=TERM --kill-after=10 7000 python -u ml/stage129_extract.py "$stage129_phase" "$stage129_index" || stage129_status=$?
    else
        /usr/bin/time -v -o "workbook/stage129_energy_ml/${stage129_phase}_${stage129_index}_time.txt" timeout --signal=TERM --kill-after=10 7000 python -u "ml/stage129_${stage129_phase}.py" "$stage129_index" || stage129_status=$?
    fi
else
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o "workbook/stage129_energy_ml/${stage129_phase}_${stage129_index}_time.txt" timeout --signal=TERM --kill-after=10 7000 python -u "ml/stage129_${stage129_phase}.py" "$stage129_index" || stage129_status=$?
fi
printf '%s\n' "$stage129_status" > "workbook/stage129_energy_ml/${stage129_phase}_${stage129_index}_exitcode.txt"
find workbook/stage129_energy_ml ntuples/energy_ml_stage129 ml/artifacts/stage129 -type f -newer .stage129_output_start ! -name extraction_contract.json -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage129/${stage129_phase}_${stage129_index}_result.tar.gz"
exit "$stage129_status"
