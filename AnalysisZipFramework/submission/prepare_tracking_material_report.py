#!/usr/bin/env python3
"""Freeze full material comparison report and stage inputs to batch scratch."""
import argparse
from pathlib import Path
import tarfile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name', required=True)
    p.add_argument('--manifest', action='append', required=True, help='label=manifest path')
    p.add_argument('--partial', action='store_true')
    args = p.parse_args()
    repo = Path(__file__).resolve().parents[2]
    submit = Path.home() / 'condor/nu_muAnalysis/stage205_material' / (args.name + '_report')
    submit.mkdir(parents=True, exist_ok=True)
    labels = []
    with tarfile.open(submit / 'code.tar.gz', 'w:gz') as tar:
        for name in ['report_tracking_material', 'report_tracking_station', 'report_tracking_ablation',
                     'extract_tracking_station', 'run_tracking_georotation', 'compare_tracking', 'report_tracking_comparison']:
            path = f'AnalysisZipFramework/scripts/{name}.py'; tar.add(repo/path, arcname=path)
        for path in ['AnalysisZipFramework/config/cuts.yaml', 'workbook/stage203_station_truth/selection_definition.json']:
            tar.add(repo/path, arcname=path)
        for item in args.manifest:
            label, path = item.split('=',1); labels.append(label)
            tar.add(path, arcname=f'{label}.tsv')
    worker = '''#!/usr/bin/env bash
set -eo pipefail
material_report_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_material205.XXXXXX")
trap 'rm -rf "$material_report_scratch"' EXIT
tar -xzf code.tar.gz -C "$material_report_scratch"
cd "$material_report_scratch"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p inputs report workbook/stage203_station_truth
/usr/bin/time -v -o report/staging_resources.txt python - <<'PYCODE'
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
for label in LABELS:
    rows=[r.split('\t') for r in Path(label+'.tsv').read_text().splitlines()]
    Path('report/'+label+'_input_manifest.tsv').write_text(Path(label+'.tsv').read_text())
    def stage(row):
        target='inputs/'+label+'_'+Path(row[5]).name
        subprocess.run(['xrdcp','--silent','root://eoshome-x.cern.ch/'+row[5],target],check=True)
        row[5]=target
        return row
    with ThreadPoolExecutor(max_workers=4) as pool: rows=list(pool.map(stage,rows))
    Path(label+'.tsv').write_text(''.join('\t'.join(r)+'\n' for r in rows))
for version in ['old','new']:
    path='workbook/stage203_station_truth/'+version+'.npz'
    subprocess.run(['xrdcp','--silent','root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/'+path,path],check=True)
PYCODE
/usr/bin/time -v -o report/report_resources.txt python AnalysisZipFramework/scripts/report_tracking_material.py --repo . --output report MANIFEST_OPTIONS PARTIAL
tar -cf report.tar -C report .
xrdcp --silent --force report.tar root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_ablation_205_material/report_NAME.tar
xrdcp --silent root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_ablation_205_material/report_NAME.tar report-roundtrip.tar
cmp report.tar report-roundtrip.tar
stat -c 'archive_roundtrip_exact bytes=%s' report.tar
echo completed material comparison report
'''
    worker = worker.replace("split('\t')", "split('\\t')").replace("'\t'.join(r)+'\n'", "'\\t'.join(r)+'\\n'")
    worker = worker.replace('LABELS', repr(labels)).replace('MANIFEST_OPTIONS', ' '.join('--manifest '+label+'='+label+'.tsv' for label in labels))
    worker = worker.replace('PARTIAL', '--allow-partial' if args.partial else '').replace('report_NAME.tar', 'report_'+args.name+'.tar')
    (submit/'worker.sh').write_text(worker); (submit/'worker.sh').chmod(0o755)
    (submit/'report.sub').write_text(f'''universe = vanilla
initialdir = {submit}
executable = {submit}/worker.sh
transfer_input_files = {submit}/code.tar.gz
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 2
request_memory = 12000MB
request_disk = 6500MB
getenv = False
+JobFlavour = "workday"
+NuMuStage = "stage205_material_report"
log = {submit}/events.log
output = {submit}/$(ClusterId).out
error = {submit}/$(ClusterId).err
queue
''')
    print(submit/'report.sub')


if __name__ == '__main__':
    main()
