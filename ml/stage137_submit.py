"""Immutable same-support packages, bounded concurrency and no application timeout."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage137_energy_ml'
SPOOL = Path('/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage137')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('phase', choices=['production','analysis'])
    parser.add_argument('--indices', nargs='+', type=int, default=[0])
    args=parser.parse_args()
    p=json.loads((OUT/'protocol.json').read_text())
    if args.phase=='production' and args.indices!=[0]:
        assert json.loads((OUT/'batch0_admission.json').read_text())['admitted']
    previous=list(OUT.glob(args.phase+'_submission_*.json'))
    submitted={i for path in previous for i in json.loads(path.read_text())['indices']}
    assert not submitted.intersection(args.indices), 'Inspect prior attempts; do not silently rerun'
    stamp=time.time_ns();relative=f'software/stage137/{stamp}/energy-ml-stage137.tar.gz'
    package=ROOT/relative;package.parent.mkdir(parents=True)
    (ROOT/'ntuples/energy_ml_stage137').mkdir(exist_ok=True)
    files=[str(path.relative_to(ROOT)) for path in (ROOT/'ml').glob('*.py')]
    files+=['ml/configs','setup_env.sh','workbook/stage137_energy_ml/protocol.json']
    if args.phase=='production':
        files+=['ntuples/energy_ml_stage131/production_cases.json.gz',
                'ntuples/energy_ml_stage131/parent_evidence.json.gz',
                'software/stage135/observer-runtime.tar.gz']
    else:
        files+=['ntuples/energy_ml_stage131/matched_input.npz',
                'ntuples/energy_ml_stage131/bootstrap_draws.npz',
                'ntuples/energy_ml_stage131/production_cases.json.gz',
                'ntuples/energy_ml_stage131/parent_evidence.json.gz',
                'ml/artifacts/stage134/energy_predictions.npz']
        files += [str(path.relative_to(ROOT)) for path in
                  (ROOT/'ntuples/energy_ml_stage137').glob('production_*_result.tar.gz')]
        assert len([s for s in files if 'production_' in s and s.endswith('.tar.gz')])==len(p['batches'])
        files += [f'workbook/stage135_energy_ml/parent_{i}_{kind}.json'
                  for i in p['pilot_reused'] for kind in ['report','hitscheck']]
    with tarfile.open(package,'w:gz') as archive:
        for name in dict.fromkeys(files):archive.add(ROOT/name,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    worker=SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage137.sh').read_bytes())
    cpus=8 if args.phase=='production' else 4
    descriptor=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} {args.phase} $(task_index)
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = {cpus}
request_memory = {24000 if args.phase=='production' else 12000}MB
request_disk = 12000MB
max_retries = 0
+MaxRuntime = 86400
+NuMuStage = "energy-ml-stage137"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
max_materialize = 24
max_idle = 24
queue task_index in {','.join(map(str,args.indices))}
'''
    sub=SPOOL/f'{args.phase}_{stamp}.sub';sub.write_text(descriptor)
    result=subprocess.check_output(['condor_submit','-terse',str(sub)],text=True).strip()
    record=dict(result=result,phase=args.phase,indices=args.indices,cpus=cpus,
                descriptor=descriptor,package=dict(path=relative,bytes=package.stat().st_size,files=files))
    (OUT/f'{args.phase}_submission_{stamp}.json').write_text(json.dumps(record,indent=2)+'\n')
    print(result)

if __name__=='__main__':main()
