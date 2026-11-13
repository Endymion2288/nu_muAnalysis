#!/usr/bin/env bash
set -eo pipefail
report_kind="${1:-overview}"
report_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_geo201_report.XXXXXX")
trap 'rm -rf "$report_scratch"' EXIT
tar -xzf tracking-georotation-report.tar.gz -C "$report_scratch"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
cd "$report_scratch"
mkdir report
cp manifest.tsv report/input_manifest.tsv
/usr/bin/time -v -o report/input_staging_resources.txt python - "$report_kind" <<'PY'
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess,sys
kind=sys.argv[1]
rows=[line.split('\t') for line in Path('manifest.tsv').read_text().splitlines()]
Path('inputs').mkdir()
def stage(row):
    index=-1 if kind=='details' else 5
    source=row[index]
    target=str(Path('inputs')/Path(source).name)
    subprocess.run(['xrdcp','--silent','root://eoshome-x.cern.ch/'+source,target],check=True)
    row[index]=target
    return row
with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(stage,rows))
Path('manifest.tsv').write_text(''.join('\t'.join(row)+'\n' for row in rows))
PY
if [[ "$report_kind" == validate ]]; then
    xrdcp --silent root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_georotation_stage201/report.tar overview.tar
    mkdir combined
    tar -xf overview.tar -C combined
    xrdcp --silent root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_georotation_stage201/report_details.tar details.tar
    mkdir details_combined
    tar -xf details.tar -C details_combined
    cp workbook/stage201_tracking/{software_provenance,recovery53_audit}.json combined/
    /usr/bin/time -v -o report/validation_resources.txt python AnalysisZipFramework/scripts/validate_tracking_georotation_storage.py \
        --manifest report/input_manifest.tsv --combined combined --local-shards inputs --audit report/storage_validation.json \
        --details-manifest details_manifest.tsv --details-combined details_combined
    report_target=report_validation.tar
elif [[ "$report_kind" == details ]]; then
    report_script=report_tracking_georotation_details.py
    report_target=report_details.tar
else
    report_script=report_tracking_georotation.py
    report_target=report.tar
fi
if [[ "$report_kind" != validate ]]; then
    /usr/bin/time -v -o report/report_resources.txt python "AnalysisZipFramework/scripts/$report_script" \
        --repo "$report_scratch" --manifest manifest.tsv --output report
fi
tar -cf report.tar -C report .
xrdcp --silent --force report.tar "root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_georotation_stage201/$report_target"
echo "completed stage201 report"
