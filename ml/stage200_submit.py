"""Submit the pilot-validated minimal vertex extraction on the existing MC."""
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage200_vertex'
SPOOL = Path.home() / 'condor/nu_muAnalysis/stage200_vertex'


def main():
    pilot = json.loads((OUT / 'pilot_4.json').read_text())
    assert pilot['files'][0]['pilot_native_standard_exact']
    SPOOL.joinpath('logs').mkdir(parents=True, exist_ok=True)
    package = ROOT / 'software/vertex-stage200.tar.gz'
    with tarfile.open(package, 'w:gz', compresslevel=1) as archive:
        for path in ['ml/stage200_vertex.py', 'AnalysisZipFramework/config',
                     'AnalysisZipFramework/include', 'build/analysis',
                     'workbook/stage200_vertex/protocol.json', 'workbook/stage200_vertex/deferred_cuts.yaml']:
            archive.add(ROOT / path, arcname=path)
    worker = SPOOL / 'worker_v1.sh'
    worker.write_bytes((ROOT / 'AnalysisZipFramework/submission/run_stage200_vertex.sh').read_bytes())
    descriptor = f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} $(Process)
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/software/vertex-stage200.tar.gz
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 4
request_memory = 5000MB
request_disk = 1000MB
max_retries = 0
+MaxRuntime = 3600
+NuMuStage = "stage200-vertex"
log = {SPOOL}/logs/$(ClusterId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 16
'''
    path = SPOOL / 'vertex_v1.sub'
    path.write_text(descriptor)
    result = subprocess.check_output(['condor_submit', '-terse', str(path)], text=True)
    (OUT / 'submission.json').write_text(json.dumps(dict(result=result, descriptor=descriptor,
         package_bytes=package.stat().st_size), indent=2) + '\n')
    print(result)


if __name__ == '__main__':
    main()
