#!/usr/bin/env bash
set -eo pipefail
stage176_phase=$1
stage176_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage176.XXXXXX")
tar -xzf energy-ml-stage176.tar.gz -C "$stage176_work"
cd "$stage176_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 NU_MU_SKIP_LCG=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage176_energy_ml ntuples/energy_ml_stage176 software/stage176
touch .stage176_start
stage176_status=0
if [[ "$stage176_phase" == audit ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o workbook/stage176_energy_ml/audit_time.txt python -u ml/stage176_audit.py || stage176_status=$?
else
    source setup_env.sh
    nu_mu_official_setup "$stage176_work/runtime"
if [[ "$stage176_phase" == preflight ]]; then
    /usr/bin/time -v -o workbook/stage176_energy_ml/build_time.txt bash -c '
        set -e
        cmake -S ml/stage176_observer -B observer-build
        cmake --build observer-build -j4
        stage176_platform=$(find observer-build -mindepth 2 -maxdepth 2 -name setup.sh -print -quit)
        test -n "$stage176_platform"
        stage176_platform=${stage176_platform%/setup.sh}
        tar --exclude="*.dbg" -czhf software/stage176/observer-runtime.tar.gz -C "$stage176_platform" lib python
    ' > workbook/stage176_energy_ml/build.log 2>&1 || stage176_status=$?
fi
if [[ "$stage176_status" == 0 ]]; then
    mkdir observer
    tar -xzf software/stage176/observer-runtime.tar.gz -C observer
    export LD_LIBRARY_PATH="$stage176_work/observer/lib:${LD_LIBRARY_PATH:-}"
    export PYTHONPATH="$stage176_work/observer/python:${PYTHONPATH:-}"
    export DATAPATH="$stage176_work/observer/lib:${DATAPATH:-}"
    /usr/bin/time -v -o "workbook/stage176_energy_ml/${stage176_phase}_time.txt" python -u ml/stage176_pilot.py "$stage176_phase" || stage176_status=$?
fi
fi
printf '%s\n' "$stage176_status" > "workbook/stage176_energy_ml/${stage176_phase}_exitcode.txt"
find workbook/stage176_energy_ml ntuples/energy_ml_stage176 software/stage176 -type f -newer .stage176_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage176/${stage176_phase}_result.tar.gz"
exit "$stage176_status"
