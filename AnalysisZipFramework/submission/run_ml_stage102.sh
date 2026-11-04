#!/usr/bin/env bash
set -eo pipefail
stage102_mode=$1
case "$stage102_mode" in qa|fit|report) ;; *) exit 2 ;; esac
stage102_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage102.XXXXXX")
trap 'rm -rf "$stage102_scratch"' EXIT
stage102_package=energy-ml-stage102-$stage102_mode.tar.gz
if [[ ! -f "$stage102_package" ]]; then
    stage102_package=/eos/user/x/xcheng/FASER/nu_muAnalysis/software/$stage102_package
fi
tar -xzf "$stage102_package" -C "$stage102_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
if [[ "$stage102_mode" == report ]]; then
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
else
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
fi
cd "$stage102_scratch"
mkdir -p workbook/stage102_energy_ml
stage102_status=0
if [[ -x /usr/bin/time ]]; then
    /usr/bin/time -v -o workbook/stage102_energy_ml/time_$stage102_mode.txt timeout --signal=TERM --kill-after=5 570 python -u ml/stage102_$stage102_mode.py || stage102_status=$?
else
    python - "$stage102_mode" <<'PY' || stage102_status=$?
import json, resource, subprocess, sys, time
from pathlib import Path
mode = sys.argv[1]
tick = time.perf_counter()
status = subprocess.call(['timeout', '--signal=TERM', '--kill-after=5', '570',
                          sys.executable, '-u', 'ml/stage102_'+mode+'.py'])
u = resource.getrusage(resource.RUSAGE_CHILDREN)
Path('workbook/stage102_energy_ml/time_'+mode+'.json').write_text(json.dumps(dict(
    exit_code=status, CPU_s=u.ru_utime+u.ru_stime, wall_s=time.perf_counter()-tick,
    peak_RSS_KiB=u.ru_maxrss, scope='child process inclusive imports and descendants'), indent=2)+'\n')
sys.exit(status)
PY
fi
stage102_outputs=(workbook/stage102_energy_ml)
[[ ! -d ntuples/energy_ml_stage102 ]] || stage102_outputs+=(ntuples/energy_ml_stage102)
[[ ! -d ml/artifacts/stage102 ]] || stage102_outputs+=(ml/artifacts/stage102)
tar -czf result.tar.gz "${stage102_outputs[@]}"
if [[ -n "${_CONDOR_SCRATCH_DIR:-}" ]]; then
    xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage102/result_$stage102_mode.tar.gz
else
    stage102_target=/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage102/result_$stage102_mode.tar.gz
    cp result.tar.gz "$stage102_target.tmp"
    mv "$stage102_target.tmp" "$stage102_target"
fi
exit "$stage102_status"
