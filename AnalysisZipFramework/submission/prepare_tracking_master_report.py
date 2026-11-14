#!/usr/bin/env python3
"""Stage integration summaries to worker scratch for full paired physics reduction."""
import argparse
from pathlib import Path
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--partial', action='store_true')
    parser.add_argument('--paired-old', action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    submit = Path.home() / 'condor/nu_muAnalysis/stage208_master_integration' / (args.name + '_report')
    submit.mkdir(parents=True, exist_ok=True)
    (repo / 'ntuples/tracking_master_stage208').mkdir(exist_ok=True)
    scripts = ['report_tracking_master_integration', 'report_tracking_material', 'report_tracking_station',
               'report_tracking_ablation', 'extract_tracking_station', 'run_tracking_georotation',
               'compare_tracking', 'report_tracking_comparison', 'summarize_tracking_master_integration']
    with tarfile.open(submit / 'code.tar.gz', 'w:gz') as archive:
        for name in scripts:
            path = f'AnalysisZipFramework/scripts/{name}.py'
            archive.add(repo / path, arcname=path)
        archive.add(repo / 'AnalysisZipFramework/config/cuts.yaml', arcname='AnalysisZipFramework/config/cuts.yaml')
        archive.add(args.manifest, arcname='original_manifest.tsv')
    worker = r'''#!/usr/bin/env bash
set -eo pipefail
integration_report_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_master_report208.XXXXXX")
trap 'rm -rf "$integration_report_scratch"' EXIT
tar -xzf code.tar.gz -C "$integration_report_scratch"
cd "$integration_report_scratch"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p inputs report workbook/stage203_station_truth workbook/stage205_material/full
cp original_manifest.tsv report/input_manifest.tsv
/usr/bin/time -v -o report/staging_resources.txt python - <<'PYCODE'
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
rows=[r.split('\t') for r in Path('original_manifest.tsv').read_text().splitlines()]
def stage(row):
    target='inputs/'+Path(row[5]).name
    subprocess.run(['xrdcp','--silent','root://eoshome-x.cern.ch/'+row[5],target],check=True)
    if PAIRED:
        subprocess.run(['xrdcp','--silent','root://eoshome-x.cern.ch/'+row[5].replace('latest_','old_'),target.replace('latest_','old_')],check=True)
    row[5]=target
    return row
with ThreadPoolExecutor(max_workers=4) as pool: rows=list(pool.map(stage,rows))
Path('manifest.tsv').write_text(''.join('\t'.join(row)+'\n' for row in rows))
for path in ['workbook/stage203_station_truth/old.npz','workbook/stage205_material/full/strict.npz']:
    subprocess.run(['xrdcp','--silent','root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/'+path,path],check=True)
PYCODE
/usr/bin/time -v -o report/report_resources.txt python AnalysisZipFramework/scripts/report_tracking_master_integration.py --repo . --manifest manifest.tsv --output report OPTIONS
python AnalysisZipFramework/scripts/summarize_tracking_master_integration.py --report report
tar -cf report.tar -C report .
xrdcp --silent --force report.tar root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_master_stage208/report_NAME.tar
xrdcp --silent root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_master_stage208/report_NAME.tar report-roundtrip.tar
cmp report.tar report-roundtrip.tar
stat -c 'archive_roundtrip_exact bytes=%s' report.tar
'''
    options = ('--partial ' if args.partial else '') + ('--paired-old' if args.paired_old else '')
    worker = worker.replace('PAIRED', repr(args.paired_old)).replace('OPTIONS', options).replace('report_NAME.tar', 'report_' + args.name + '.tar')
    (submit / 'worker.sh').write_text(worker)
    (submit / 'worker.sh').chmod(0o755)
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
+NuMuStage = "stage208_master_report"
log = {submit}/events.log
output = {submit}/$(ClusterId).out
error = {submit}/$(ClusterId).err
queue
''')
    print(submit / 'report.sub')


if __name__ == '__main__':
    main()
