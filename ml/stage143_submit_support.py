"""Compact cache support audit, no native stack setup or local scientific scan."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage143_energy_ml'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage143'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['support','audit'],default='support');phase=parser.parse_args().phase
    assert not (OUT/f'{phase}_submission.json').exists()
    stamp=time.time_ns();relative=f'software/stage143/{stamp}/energy-ml-stage143.tar.gz'
    p=ROOT/relative;p.parent.mkdir(parents=True)
    files=['ml/stage143_support.py','workbook/stage143_energy_ml/protocol.json',
           'ntuples/energy_ml_stage131/production_cases.json.gz','ntuples/energy_ml_stage137/boundary_evidence.json.gz']
    if phase=='audit':
        files=['ml/stage143_summarize.py','workbook/stage143_energy_ml/protocol.json','workbook/stage143_energy_ml/support.json']
        for index in json.loads((OUT/'support.json').read_text())['selected_indices']:
            files += [f'workbook/stage143_energy_ml/parent_{index}_{suffix}' for suffix in ['report.json','admission.json','lineage.json','source_control.json','source_analog_charge.tsv']]
            files += [f'ntuples/energy_ml_stage143/parent_{index}_{suffix}' for suffix in ['qa_hits.json.gz','control.json.gz']]
    with tarfile.open(p,'w:gz') as a:
        for name in files:a.add(ROOT/name,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    worker=SPOOL/f'worker_{stamp}.sh'
    worker.write_text('''#!/usr/bin/env bash
set -eo pipefail
stage143_work=$(mktemp -d "${_CONDOR_SCRATCH_DIR:-/tmp}/nu_mu_stage143.XXXXXX")
tar -xzf energy-ml-stage143.tar.gz -C "$stage143_work"
cd "$stage143_work"
mkdir -p workbook/stage143_energy_ml
stage143_status=0
/usr/bin/time -v -o workbook/stage143_energy_ml/PHASE_time.txt /usr/bin/python3 -u ml/SCRIPT.py || stage143_status=$?
printf '%s\\n' "$stage143_status" > workbook/stage143_energy_ml/PHASE_exitcode.txt
tar -czf result.tar.gz workbook/stage143_energy_ml
xrdcp --silent --force result.tar.gz root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage143/PHASE_result.tar.gz
exit "$stage143_status"
'''.replace('PHASE',phase).replace('SCRIPT','stage143_support' if phase=='support' else 'stage143_summarize'))
    descriptor=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker}
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 1
request_memory = 2000MB
request_disk = 2000MB
max_retries = 0
+MaxRuntime = 86400
+NuMuStage = "energy-ml-stage143"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
    sub=SPOOL/f'{phase}_{stamp}.sub';sub.write_text(descriptor)
    result=subprocess.check_output(['condor_submit','-terse',str(sub)],text=True).strip()
    (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(result=result,phase=phase,cpus=1,descriptor=descriptor,package=dict(path=relative,bytes=p.stat().st_size,files=files)),indent=2)+'\n');print(result)

if __name__=='__main__':main()
