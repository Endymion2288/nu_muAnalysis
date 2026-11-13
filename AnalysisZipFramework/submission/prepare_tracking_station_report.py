#!/usr/bin/env python3
"""Prepare a compact paired station report on batch nodes after pilot/production completion."""
import argparse
from pathlib import Path
import shutil
import tarfile


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--name',default='production')
    p.add_argument('--partial',action='store_true');p.add_argument('--manifest',type=Path);args=p.parse_args()
    repo=Path(__file__).resolve().parents[2];base=Path.home()/'condor/nu_muAnalysis/stage203_station_truth'
    submit=base/(args.name+'_report');submit.mkdir(parents=True,exist_ok=True)
    manifest=args.manifest or base/args.name/'manifest.tsv'
    with tarfile.open(submit/'station-report.tar.gz','w:gz') as tar:
        for name in ['report_tracking_station','validate_tracking_station_storage','extract_tracking_station','run_tracking_georotation','compare_tracking','report_tracking_comparison']:
            path=f'AnalysisZipFramework/scripts/{name}.py';tar.add(repo/path,arcname=path)
        path='AnalysisZipFramework/config/cuts.yaml';tar.add(repo/path,arcname=path)
        tar.add(manifest,arcname='manifest.tsv')
    worker=submit/'worker.sh';worker.write_text(f'''#!/usr/bin/env bash
set -eo pipefail
station_report_scratch=$(mktemp -d "${{_CONDOR_SCRATCH_DIR:-/tmp}}/nu_mu_station_report.XXXXXX")
trap 'rm -rf "$station_report_scratch"' EXIT
tar -xzf station-report.tar.gz -C "$station_report_scratch"
cd "$station_report_scratch"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir inputs report
cp manifest.tsv report/input_manifest.tsv
/usr/bin/time -v -o report/staging_resources.txt python - <<'PYCODE'
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
rows=[r.split('\\t') for r in Path('manifest.tsv').read_text().splitlines()]
def stage(r):
    target=str(Path('inputs')/Path(r[5]).name)
    subprocess.run(['xrdcp','--silent','root://eoshome-x.cern.ch/'+r[5],target],check=True)
    r[5]=target
    return r
with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(stage,rows))
Path('manifest.tsv').write_text(''.join('\\t'.join(r)+'\\n' for r in rows))
PYCODE
/usr/bin/time -v -o report/report_resources.txt python AnalysisZipFramework/scripts/report_tracking_station.py --repo . --manifest manifest.tsv --output report {'--allow-partial' if args.partial else ''}
{'xrdcp --silent root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/workbook/stage201_tracking/candidate_diagnostics.npz previous_candidates.npz' if not args.partial else ''}
/usr/bin/time -v -o report/validation_resources.txt python AnalysisZipFramework/scripts/validate_tracking_station_storage.py --manifest manifest.tsv --combined report --output report/storage_validation.json {'--previous-candidates previous_candidates.npz' if not args.partial else ''}
tar -cf report.tar -C report .
xrdcp --silent --force report.tar root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_station_stage203/report_{args.name}.tar
echo completed station report
''');worker.chmod(0o755)
    (submit/'report.sub').write_text(f'''universe = vanilla
initialdir = {submit}
executable = {worker}
transfer_input_files = {submit}/station-report.tar.gz
should_transfer_files = YES
transfer_output_files = ""
when_to_transfer_output = ON_EXIT
request_cpus = 2
request_memory = 6000MB
request_disk = 6000MB
getenv = False
+JobFlavour = "microcentury"
+NuMuStage = "stage203_station_report"
log = {submit}/events.log
output = {submit}/$(ClusterId).out
error = {submit}/$(ClusterId).err
queue
''')
    print(submit/'report.sub')


if __name__=='__main__':main()
