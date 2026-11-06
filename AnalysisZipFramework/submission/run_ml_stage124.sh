#!/usr/bin/env bash
set -eo pipefail
stage124_phase=$1
stage124_index=${2:-0}
stage124_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage124.XXXXXX")
tar -xzf "energy-ml-stage124-${stage124_phase}.tar.gz" -C "$stage124_work"
cd "$stage124_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage124_energy_ml ntuples/energy_ml_stage124 result
stage124_status=0
if [[ "$stage124_phase" == prepare || "$stage124_phase" == fit || "$stage124_phase" == validate || "$stage124_phase" == support || "$stage124_phase" == qa || "$stage124_phase" == engineering ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o "workbook/stage124_energy_ml/${stage124_phase}_time.txt" timeout --signal=TERM --kill-after=10 7000 python -u "ml/stage124_${stage124_phase}.py" || stage124_status=$?
    tar -czf result.tar.gz workbook/stage124_energy_ml ntuples/energy_ml_stage124 ml/artifacts/stage124 2>/dev/null || tar -czf result.tar.gz workbook/stage124_energy_ml ntuples/energy_ml_stage124
else
    export NU_MU_SKIP_LCG=1
    source setup_env.sh
    nu_mu_official_setup "$stage124_work/runtime"
    /usr/bin/time -v -o "result/native_time.txt" timeout --signal=TERM --kill-after=10 7000 python -u ml/stage124_native.py "$stage124_index" "$stage124_phase" 2>&1 | tee result/native_log.txt || stage124_status=$?
    printf '%s\n' "$stage124_status" > result/exitcode.txt
    tar -czf result.tar.gz result
fi
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage124/${stage124_phase}_${stage124_index}_result.tar.gz"
exit "$stage124_status"
