#!/usr/bin/env bash
set -eo pipefail
stage135_phase=$1
stage135_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage135.XXXXXX")
tar -xzf energy-ml-stage135.tar.gz -C "$stage135_work"
cd "$stage135_work"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 NU_MU_SKIP_LCG=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
mkdir -p workbook/stage135_energy_ml ntuples/energy_ml_stage135 software/stage135
touch .stage135_start
stage135_status=0
if [[ "$stage135_phase" == audit ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
    /usr/bin/time -v -o workbook/stage135_energy_ml/audit_time.txt python -u ml/stage135_summarize.py || stage135_status=$?
else
    source setup_env.sh
    nu_mu_official_setup "$stage135_work/runtime"
if [[ "$stage135_phase" == preflight ]]; then
    /usr/bin/time -v -o workbook/stage135_energy_ml/build_time.txt bash -c '
        set -e
        cmake -S ml/stage135_observer -B observer-build
        cmake --build observer-build -j4
        stage135_platform=$(find observer-build -mindepth 2 -maxdepth 2 -name setup.sh -print -quit)
        test -n "$stage135_platform"
        stage135_platform=${stage135_platform%/setup.sh}
        tar --exclude="*.dbg" -czhf software/stage135/observer-runtime.tar.gz -C "$stage135_platform" lib python
    ' > workbook/stage135_energy_ml/build.log 2>&1 || stage135_status=$?
fi
if [[ "$stage135_status" == 0 ]]; then
    mkdir observer
    tar -xzf software/stage135/observer-runtime.tar.gz -C observer
    export LD_LIBRARY_PATH="$stage135_work/observer/lib:${LD_LIBRARY_PATH:-}"
    export PYTHONPATH="$stage135_work/observer/python:${PYTHONPATH:-}"
    export DATAPATH="$stage135_work/observer/lib:${DATAPATH:-}"
    /usr/bin/time -v -o "workbook/stage135_energy_ml/${stage135_phase}_time.txt" python -u ml/stage135_pilot.py "$stage135_phase" || stage135_status=$?
fi
fi
printf '%s\n' "$stage135_status" > "workbook/stage135_energy_ml/${stage135_phase}_exitcode.txt"
find workbook/stage135_energy_ml ntuples/energy_ml_stage135 software/stage135 -type f -newer .stage135_start -print0 | tar --null -czf result.tar.gz -T -
xrdcp --silent --force result.tar.gz "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage135/${stage135_phase}_result.tar.gz"
exit "$stage135_status"
