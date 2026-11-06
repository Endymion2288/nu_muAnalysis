"""Submit immutable coordinate extraction or cached rectangle-scan packages."""
import argparse
import json
import subprocess
import tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage127_energy_ml'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage127'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['coordinates','scan']);a=parser.parse_args()
    assert json.loads((OUT/'native_pilot.json').read_text())['passed']
    paths=['ml/stage127_coordinates.py','workbook/stage127_energy_ml/protocol.json','ntuples/energy_ml_stage126/predictions.npz']
    if a.phase=='coordinates':
        paths+=['ntuples/energy_ml_stage127/anchor.npz'];cores=4;count=8
    else:
        paths+=['ntuples/energy_ml_stage127/coordinates.npz','ml/stage127_scan.py','ml/stage127_native.py',
                'ml/stage126_report.py','ml/audited_features.py','ml/configs/audited_features.json',
                'AnalysisZipFramework/config/ml_low_energy_cuts.yaml'];cores=8;count=1
    package=ROOT/f'software/energy-ml-stage127-{a.phase}.tar.gz'
    with tarfile.open(package,'w:gz',compresslevel=1) as archive:
        for path in paths:archive.add(ROOT/path,arcname=path)
    (SPOOL/'logs').mkdir(parents=True,exist_ok=True)
    worker=SPOOL/f'{a.phase}_v1.sh';worker.write_bytes((ROOT/f'AnalysisZipFramework/submission/run_ml_stage127_{a.phase}.sh').read_bytes())
    descriptor=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} $(Process)
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/software/energy-ml-stage127-{a.phase}.tar.gz
should_transfer_files = YES
transfer_output_files = ""
request_cpus = {cores}
request_memory = 6000MB
request_disk = 1000MB
max_retries = 0
+MaxRuntime = 3600
+NuMuStage = "energy-ml-stage127-{a.phase}"
log = {SPOOL}/logs/$(ClusterId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue {count}
'''
    path=SPOOL/f'{a.phase}_v1.sub';path.write_text(descriptor)
    result=subprocess.check_output(['condor_submit','-terse',str(path)],text=True)
    (OUT/f'submission_{a.phase}.json').write_text(json.dumps(dict(result=result,descriptor=descriptor,package_bytes=package.stat().st_size),indent=2)+'\n')
    print(result)


if __name__=='__main__':main()
