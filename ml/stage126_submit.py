"""Package a validated fixed-model radius scan and submit 16 four-core batches."""
import json
import subprocess
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage126_energy_ml'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage126'

def main():
    pilot=json.loads((OUT/'pilot_4.json').read_text())
    assert pilot['results'][0]['baseline62_exact_N']>0
    package=ROOT/'software/energy-ml-stage126.tar.gz'
    with tarfile.open(package,'w:gz',compresslevel=1) as archive:
        for f in sorted((ROOT/'ml').glob('*.py')):archive.add(f,arcname=str(f.relative_to(ROOT)))
        for f in ['ml/configs','AnalysisZipFramework/config','AnalysisZipFramework/include','build/analysis',
                  'ntuples/energy_ml_stage55/dataset.npz','ntuples/energy_ml_stage56/readout.npz',
                  'workbook/stage126_energy_ml/protocol.json','workbook/stage126_energy_ml/scan_cuts.yaml']:
            archive.add(ROOT/f,arcname=f)
        for seed in [2026110255,2026110256,2026110257]:
            f=f'ml/artifacts/stage87/direct_{seed}.ubj';archive.add(ROOT/f,arcname=f)
    (SPOOL/'logs').mkdir(parents=True,exist_ok=True)
    worker=SPOOL/'worker_v1.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage126.sh').read_bytes())
    descriptor=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} $(Process)
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/software/energy-ml-stage126.tar.gz
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 4
request_memory = 6000MB
request_disk = 2000MB
max_retries = 0
+MaxRuntime = 3600
+NuMuStage = "energy-ml-stage126"
log = {SPOOL}/logs/$(ClusterId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 16
'''
    path=SPOOL/'radius_v1.sub';path.write_text(descriptor)
    result=subprocess.check_output(['condor_submit','-terse',str(path)],text=True)
    (OUT/'submission.json').write_text(json.dumps(dict(result=result,descriptor=descriptor,package_bytes=package.stat().st_size),indent=2)+'\n')
    print(result)

if __name__=='__main__':main()
