#!/usr/bin/env python3
"""Freeze the old/strict cached-selection inventory and submit its full reduction."""
from pathlib import Path
import tarfile


def main():
    repo = Path(__file__).resolve().parents[2]
    submit = Path.home() / 'condor/nu_muAnalysis/stage206_old_strict'
    submit.mkdir(parents=True, exist_ok=True)
    (repo / 'ntuples/tracking_properties_stage206').mkdir(exist_ok=True)
    names = ['report_tracking_old_strict_properties', 'report_tracking_material', 'report_tracking_station',
             'report_tracking_ablation', 'compare_tracking', 'extract_tracking_station',
             'run_tracking_georotation', 'report_tracking_comparison']
    with tarfile.open(submit / 'code.tar.gz', 'w:gz') as tar:
        for name in names:
            rel = f'AnalysisZipFramework/scripts/{name}.py'; tar.add(repo / rel, arcname=rel)
    worker = '''#!/usr/bin/env bash
set -eo pipefail
properties_scratch=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_properties206.XXXXXX")
trap 'rm -rf "$properties_scratch"' EXIT
tar -xzf code.tar.gz -C "$properties_scratch"
cd "$properties_scratch"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
source /cvmfs/sft.cern.ch/lcg/views/LCG_109/x86_64-el9-gcc15-opt/setup.sh
mkdir -p workbook/stage203_station_truth workbook/stage205_material/full report
/usr/bin/time -v -o report/staging_resources.txt bash -c '
xrdcp --silent root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/workbook/stage203_station_truth/old.npz workbook/stage203_station_truth/old.npz
xrdcp --silent root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/workbook/stage205_material/full/strict.npz workbook/stage205_material/full/strict.npz'
/usr/bin/time -v -o report/report_resources.txt python AnalysisZipFramework/scripts/report_tracking_old_strict_properties.py --repo . --output report
tar -cf report.tar -C report .
xrdcp --silent --force report.tar root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_properties_stage206/report.tar
xrdcp --silent root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/tracking_properties_stage206/report.tar roundtrip.tar
cmp report.tar roundtrip.tar
stat -c 'archive_roundtrip_exact bytes=%s' report.tar
'''
    (submit/'worker.sh').write_text(worker); (submit/'worker.sh').chmod(0o755)
    (submit/'report.sub').write_text(f'''universe = vanilla
initialdir = {submit}
executable = {submit}/worker.sh
transfer_input_files = {submit}/code.tar.gz
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 1
request_memory = 6000MB
request_disk = 2000MB
getenv = False
+JobFlavour = "workday"
+NuMuStage = "stage206_old_strict"
log = {submit}/events.log
output = {submit}/$(ClusterId).out
error = {submit}/$(ClusterId).err
queue
''')
    print(submit/'report.sub')


if __name__ == '__main__':
    main()
