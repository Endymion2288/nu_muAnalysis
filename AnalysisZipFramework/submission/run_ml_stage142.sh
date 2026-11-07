#!/usr/bin/env bash
set -eo pipefail
stage142_phase=$1
stage142_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage142.XXXXXX")
tar -xzf energy-ml-stage142.tar.gz -C "$stage142_work"
cd "$stage142_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 NU_MU_SKIP_LCG=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage142_energy_ml ntuples/energy_ml_stage142 software/stage142
touch .stage142_start
stage142_status=0
if [[ "$stage142_phase" == audit ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o workbook/stage142_energy_ml/audit_time.txt python -u ml/stage142_summarize.py || stage142_status=$?
else
    source setup_env.sh
    nu_mu_official_setup "$stage142_work/runtime"
if [[ "$stage142_phase" == preflight ]]; then
    /usr/bin/time -v -o workbook/stage142_energy_ml/build_time.txt bash -c '
        set -e
        cmake -S ml/stage142_observer -B observer-build
        cmake --build observer-build -j4
        stage142_platform=$(find observer-build -mindepth 2 -maxdepth 2 -name setup.sh -print -quit)
        test -n "$stage142_platform"
        stage142_platform=${stage142_platform%/setup.sh}
        tar --exclude="*.dbg" -czhf software/stage142/observer-runtime.tar.gz -C "$stage142_platform" lib python
    ' > workbook/stage142_energy_ml/build.log 2>&1 || stage142_status=$?
fi
if [[ "$stage142_status" == 0 ]]; then
    mkdir observer
    tar -xzf software/stage142/observer-runtime.tar.gz -C observer
    export LD_LIBRARY_PATH="$stage142_work/observer/lib:${LD_LIBRARY_PATH:-}"
    export PYTHONPATH="$stage142_work/observer/python:${PYTHONPATH:-}"
    export DATAPATH="$stage142_work/observer/lib:${DATAPATH:-}"
    /usr/bin/time -v -o "workbook/stage142_energy_ml/${stage142_phase}_time.txt" python -u ml/stage142_pilot.py "$stage142_phase" || stage142_status=$?
fi
fi
printf '%s\n' "$stage142_status" > "workbook/stage142_energy_ml/${stage142_phase}_exitcode.txt"
find workbook/stage142_energy_ml ntuples/energy_ml_stage142 software/stage142 -type f -newer .stage142_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage142/${stage142_phase}_result.tar.gz"
exit "$stage142_status"
