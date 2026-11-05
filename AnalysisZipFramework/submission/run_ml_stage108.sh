#!/usr/bin/env bash
set -eo pipefail
stage108_mode=$1
case "$stage108_mode" in qa_extract|qa|train_extract|fit|test_extract|infer|report) ;; *) exit 2 ;; esac
stage108_repo=/eos/user/x/xcheng/FASER/nu_muAnalysis
stage108_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage108.XXXXXX")
trap 'rm -rf "$stage108_scratch"' EXIT
stage108_package=energy-ml-stage108-$stage108_mode.tar.gz
[[ -f "$stage108_package" ]] || stage108_package=$stage108_repo/software/$stage108_package
stage108_package=$(readlink -f "$stage108_package")
tar -xzf "$stage108_package" -C "$stage108_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
stage108_timeout=3500
case "$stage108_mode" in
 qa|fit|infer)
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
    stage108_timeout=10200 ;;
 *) source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh ;;
esac
cd "$stage108_scratch"
mkdir -p ntuples/energy_ml_stage108 ml/artifacts/stage108
stage108_status=0
timeout --signal=TERM --kill-after=5 "$stage108_timeout" python -u ml/time_stage108.py "$stage108_mode" || stage108_status=$?
# Only new outputs; returning immutable inputs would duplicate coordinate/payload caches.
python - "$stage108_mode" "$stage108_package" <<'PY'
import sys,tarfile
from pathlib import Path
mode,package=sys.argv[1:]
with tarfile.open(package) as t:original={m.name for m in t.getmembers() if m.isfile()}
with tarfile.open('result.tar.gz','w:gz',compresslevel=1) as t:
 for folder in ['workbook/stage108_energy_ml','ntuples/energy_ml_stage108','ml/artifacts/stage108']:
  for p in sorted(Path(folder).rglob('*')):
   if p.is_file() and str(p) not in original:t.add(p,arcname=str(p))
PY
stage108_target=$stage108_repo/ntuples/energy_ml_stage108/result_$stage108_mode.tar.gz
if [[ -n "${_CONDOR_SCRATCH_DIR:-}" ]]; then
    xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch/$stage108_target
else
    cp result.tar.gz "$stage108_target.tmp"
    mv "$stage108_target.tmp" "$stage108_target"
fi
exit "$stage108_status"
