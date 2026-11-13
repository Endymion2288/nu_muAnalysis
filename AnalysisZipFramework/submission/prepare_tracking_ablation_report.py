#!/usr/bin/env python3
"""Stage compact control shards and stage203 baselines locally before batch reduction."""
import argparse
from pathlib import Path
import tarfile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name', required=True)
    args = p.parse_args()
    repo = Path(__file__).resolve().parents[2]
    base = Path.home() / 'condor/nu_muAnalysis/stage204_causal'
    submit = base / (args.name + '_report')
    submit.mkdir(parents=True, exist_ok=True)
    with tarfile.open(submit / 'code.tar.gz', 'w:gz') as tar:
        for name in ['report_tracking_ablation', 'report_tracking_station', 'extract_tracking_station',
                     'run_tracking_georotation', 'compare_tracking', 'report_tracking_comparison']:
            path = f'AnalysisZipFramework/scripts/{name}.py'
            tar.add(repo / path, arcname=path)
        tar.add(repo / 'AnalysisZipFramework/config/cuts.yaml', arcname='AnalysisZipFramework/config/cuts.yaml')
        tar.add(base / args.name / 'manifest.tsv', arcname='original_manifest.tsv')
    script = '''#!/usr/bin/env bash
set -eo pipefail
ablation_report_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_ablation_report.XXXXXX")
trap 'rm -rf "$ablation_report_scratch"' EXIT
tar -xzf code.tar.gz -C "$ablation_report_scratch"
cd "$ablation_report_scratch"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p inputs report workbook/stage203_station_truth
cp original_manifest.tsv report/input_manifest.tsv
/usr/bin/time -v -o report/staging_resources.txt python - <<'PYCODE'
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
rows=[r.split('\t') for r in Path('original_manifest.tsv').read_text().splitlines()]
def stage(r):
    target=str(Path('inputs')/Path(r[5]).name)
    subprocess.run(['xrdcp','--silent','root://eoshome-x.cern.ch/'+r[5],target],check=True)
    r[5]=target
    return r
with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(stage,rows))
Path('manifest.tsv').write_text(''.join('\t'.join(r)+'\n' for r in rows))
for v in ['old','new']:
    name='workbook/stage203_station_truth/'+v+'.npz'
    subprocess.run(['xrdcp','--silent','root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/'+name,name],check=True)
PYCODE
/usr/bin/time -v -o report/report_resources.txt python AnalysisZipFramework/scripts/report_tracking_ablation.py --repo . --manifest manifest.tsv --output report --validate-baselines
tar -cf report.tar -C report .
xrdcp --silent --force report.tar root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_ablation_stage204/report_NAME.tar
echo completed ablation report
'''
    # Keep literal backslashes in the embedded Python program.
    script = script.replace("split('\t')", "split('\\t')").replace("'\t'.join(r)+'\n'", "'\\t'.join(r)+'\\n'")
    (submit / 'worker.sh').write_text(script.replace('report_NAME.tar', 'report_'+args.name+'.tar'))
    (submit / 'worker.sh').chmod(0o755)
    (submit / 'report.sub').write_text(f'''universe = vanilla
initialdir = {submit}
executable = {submit}/worker.sh
transfer_input_files = {submit}/code.tar.gz
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 2
request_memory = 4500MB
request_disk = 3000MB
getenv = False
+JobFlavour = "microcentury"
+NuMuStage = "stage204_causal_report"
log = {submit}/events.log
output = {submit}/$(ClusterId).out
error = {submit}/$(ClusterId).err
queue
''')
    print(submit / 'report.sub')


if __name__ == '__main__':
    main()
