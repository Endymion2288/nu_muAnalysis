#!/usr/bin/env python3
"""Stage compact reconstruction shards and frozen references for batch reduction."""
import argparse
from pathlib import Path
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--partial', action='store_true')
    args = parser.parse_args(); repo = Path(__file__).resolve().parents[2]
    submit = Path.home() / 'condor/nu_muAnalysis/stage210_covariance' / (args.name + '_report')
    submit.mkdir(parents=True, exist_ok=True)
    (repo / 'ntuples/tracking_covariance_stage210').mkdir(exist_ok=True)
    scripts = ['report_tracking_covariance', 'summarize_tracking_covariance',
        'report_tracking_master_integration', 'report_tracking_material', 'report_tracking_station',
        'report_tracking_ablation', 'extract_tracking_station', 'run_tracking_georotation',
        'compare_tracking', 'report_tracking_comparison']
    with tarfile.open(submit / 'code.tar.gz', 'w:gz') as archive:
        for name in scripts:
            path = f'AnalysisZipFramework/scripts/{name}.py'
            archive.add(repo / path, arcname=path)
        archive.add(repo / 'AnalysisZipFramework/config/cuts.yaml', arcname='AnalysisZipFramework/config/cuts.yaml')
        archive.add(args.manifest, arcname='original_manifest.tsv')
    worker = r'''#!/usr/bin/env bash
set -eo pipefail
covariance_report_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_covariance_report210.XXXXXX")
trap 'rm -rf "$covariance_report_scratch"' EXIT
tar -xzf code.tar.gz -C "$covariance_report_scratch"
cd "$covariance_report_scratch"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p inputs report workbook/stage203_station_truth workbook/stage208_master_integration/full
cp original_manifest.tsv report/input_manifest.tsv
/usr/bin/time -v -o report/staging_resources.txt python - <<'PYCODE'
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
rows=[r.split('\t') for r in Path('original_manifest.tsv').read_text().splitlines() if r.split('\t')[6]=='small']
def stage(row):
    target='inputs/'+Path(row[5]).name
    subprocess.run(['xrdcp','--silent','root://eoshome-x.cern.ch/'+row[5],target],check=True)
    row[5]=target
    return row
with ThreadPoolExecutor(max_workers=4) as pool: rows=list(pool.map(stage,rows))
Path('manifest.tsv').write_text(''.join('\t'.join(row)+'\n' for row in rows))
for path in ['workbook/stage203_station_truth/old.npz','workbook/stage208_master_integration/full/latest.npz']:
    subprocess.run(['xrdcp','--silent','root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/'+path,path],check=True)
PYCODE
/usr/bin/time -v -o report/report_resources.txt python AnalysisZipFramework/scripts/report_tracking_covariance.py --repo . --manifest manifest.tsv --output report OPTIONS
python AnalysisZipFramework/scripts/summarize_tracking_covariance.py --report report
tar -cf report.tar -C report .
xrdcp --silent --force report.tar root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_covariance_stage210/report_NAME.tar
xrdcp --silent root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_covariance_stage210/report_NAME.tar report-roundtrip.tar
cmp report.tar report-roundtrip.tar
stat -c 'archive_roundtrip_exact bytes=%s' report.tar
'''
    worker = worker.replace('OPTIONS', '--partial' if args.partial else '').replace('report_NAME.tar', 'report_' + args.name + '.tar')
    (submit / 'worker.sh').write_text(worker); (submit / 'worker.sh').chmod(0o755)
    (submit / 'report.sub').write_text(f'''universe = vanilla
initialdir = {submit}
executable = {submit}/worker.sh
transfer_input_files = {submit}/code.tar.gz
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 2
request_memory = 10000MB
request_disk = 5000MB
getenv = False
+JobFlavour = "workday"
+NuMuStage = "stage210_covariance_report"
log = {submit}/events.log
output = {submit}/$(ClusterId).out
error = {submit}/$(ClusterId).err
queue
''')
    print(submit / 'report.sub')


if __name__ == '__main__':
    main()
