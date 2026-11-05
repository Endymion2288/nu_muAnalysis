#!/usr/bin/env bash
set -eo pipefail
stage107_mode=$1
case "$stage107_mode" in qa_extract|qa) ;; *) exit 2 ;; esac
stage107_repo=/eos/user/x/xcheng/FASER/nu_muAnalysis
stage107_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage107.XXXXXX")
trap 'rm -rf "$stage107_scratch"' EXIT
stage107_package=energy-ml-stage107-$stage107_mode.tar.gz
[[ -f "$stage107_package" ]] || stage107_package=$stage107_repo/software/$stage107_package
stage107_package=$(readlink -f "$stage107_package")
tar -xzf "$stage107_package" -C "$stage107_scratch"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
stage107_timeout=1740
case "$stage107_mode" in
 qa)
    source /cvmfs/sft.cern.ch/lcg/views/LCG_109_cuda/x86_64-el9-gcc13-opt/setup.sh
    stage107_timeout=570 ;;
 *) source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh ;;
esac
cd "$stage107_scratch"
mkdir -p ntuples/energy_ml_stage107 ml/artifacts/stage107
stage107_status=0
timeout --signal=TERM --kill-after=5 "$stage107_timeout" python -u ml/time_stage107.py "$stage107_mode" || stage107_status=$?
# Only new outputs; returning immutable inputs would duplicate coordinate/payload caches.
python - "$stage107_mode" "$stage107_package" <<'PY'
import sys,tarfile
from pathlib import Path
mode,package=sys.argv[1:]
with tarfile.open(package) as t:original={m.name for m in t.getmembers() if m.isfile()}
with tarfile.open('result.tar.gz','w:gz',compresslevel=1) as t:
 for folder in ['workbook/stage107_energy_ml','ntuples/energy_ml_stage107','ml/artifacts/stage107']:
  for p in sorted(Path(folder).rglob('*')):
   if p.is_file() and str(p) not in original:t.add(p,arcname=str(p))
PY
stage107_target=$stage107_repo/ntuples/energy_ml_stage107/result_$stage107_mode.tar.gz
if [[ -n "${_CONDOR_SCRATCH_DIR:-}" ]]; then
    xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch/$stage107_target
else
    cp result.tar.gz "$stage107_target.tmp"
    mv "$stage107_target.tmp" "$stage107_target"
fi
exit "$stage107_status"
