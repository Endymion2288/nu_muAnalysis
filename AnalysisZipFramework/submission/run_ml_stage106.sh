#!/usr/bin/env bash
set -eo pipefail
stage106_mode=$1
case "$stage106_mode" in qa_extract|qa|train_extract|fit|test_extract|infer|report) ;; *) exit 2 ;; esac
stage106_repo=/eos/user/x/xcheng/FASER/nu_muAnalysis
stage106_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage106.XXXXXX")
trap 'rm -rf "$stage106_scratch"' EXIT
stage106_package=energy-ml-stage106-$stage106_mode.tar.gz
[[ -f "$stage106_package" ]] || stage106_package=$stage106_repo/software/$stage106_package
stage106_package=$(readlink -f "$stage106_package")
tar -xzf "$stage106_package" -C "$stage106_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
stage106_timeout=1740
case "$stage106_mode" in
 qa|fit|infer)
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
    stage106_timeout=6900 ;;
 *) source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh ;;
esac
cd "$stage106_scratch"
mkdir -p ntuples/energy_ml_stage106 ml/artifacts/stage106
stage106_status=0
timeout --signal=TERM --kill-after=5 "$stage106_timeout" python -u ml/time_stage106.py "$stage106_mode" || stage106_status=$?
# Only new outputs; returning immutable inputs would duplicate coordinate/payload caches.
python - "$stage106_mode" "$stage106_package" <<'PY'
import sys,tarfile
from pathlib import Path
mode,package=sys.argv[1:]
with tarfile.open(package) as t:original={m.name for m in t.getmembers() if m.isfile()}
with tarfile.open('result.tar.gz','w:gz',compresslevel=1) as t:
 for folder in ['workbook/stage106_energy_ml','ntuples/energy_ml_stage106','ml/artifacts/stage106']:
  for p in sorted(Path(folder).rglob('*')):
   if p.is_file() and str(p) not in original:t.add(p,arcname=str(p))
PY
stage106_target=$stage106_repo/ntuples/energy_ml_stage106/result_$stage106_mode.tar.gz
if [[ -n "${_CONDOR_SCRATCH_DIR:-}" ]]; then
    xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch/$stage106_target
else
    cp result.tar.gz "$stage106_target.tmp"
    mv "$stage106_target.tmp" "$stage106_target"
fi
exit "$stage106_status"
