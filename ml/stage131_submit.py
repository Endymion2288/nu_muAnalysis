"""Immutable Stage131 work packages; no application timeout for K showers."""
import argparse
import json
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage131_energy_ml'
SPOOL=Path('/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage131')

def submit(phase,indices=(0,),cpus=4,memory=12000):
    OUT.mkdir(exist_ok=True);(ROOT/'ntuples/energy_ml_stage131').mkdir(exist_ok=True)
    stamp=time.time_ns();relative=f'software/stage131/{stamp}/energy-ml-stage131.tar.gz'
    path=ROOT/relative;path.parent.mkdir(parents=True)
    files=[str(p.relative_to(ROOT)) for p in (ROOT/'ml').glob('*.py')]
    files+=['ml/configs','ml/stage129_rng.hxx','ml/stage131_observer',
        'AnalysisZipFramework/config','AnalysisZipFramework/include','build/analysis',
        'setup_env.sh','workbook/stage130_energy_ml/source_protocol.json',
        'workbook/stage130_energy_ml/payload_snapshot.json',
        'workbook/stage129_energy_ml/fullchain_fixed_payload.json']
    files += [str(p.relative_to(ROOT)) for p in OUT.glob('*contract.json')]
    if phase=='frame':files+=['ntuples/energy_ml_stage130/new_input.npz']
    else:files+=['ntuples/energy_ml_stage131/frame.json.gz','software/stage131/observer-runtime.tar.gz']
    if phase=='pilot' and (OUT/'preflight_results.json').exists():
        files += [str(p.relative_to(ROOT)) for p in OUT.glob('parent_50_*')]
        files += ['workbook/stage131_energy_ml/preflight_results.json','workbook/stage131_energy_ml/observer_noninterference.json','ntuples/energy_ml_stage131/parent_50_selected.npz']
    if phase in ['analysis','audit']:
        contract=json.loads((OUT/'production_contract.json').read_text())
        files += ['ntuples/energy_ml_stage131/production_cases.json.gz']
        if phase=='analysis':
            files += ['ml/artifacts/stage87/predictions.npz']
            files += [f'ml/artifacts/stage87/direct_{seed}.ubj' for seed in contract['baseline']['seeds']]
        else:
            files += ['ntuples/energy_ml_stage131/parent_evidence.json.gz']
            files += [f'workbook/stage131_energy_ml/{name}.json' for name in ['fits','independent_validation','compact_verification','rng_usage_correction']]
        files += [f'ntuples/energy_ml_stage131/production_{j}_result.tar.gz' for j in range(len(contract['batches']))]
        for i in contract['pilot_reused']:
            files += [f'workbook/stage131_energy_ml/parent_{i}_{kind}.json' for kind in ['summary','hitscheck','selection','rng']]
            files += [str(p.relative_to(ROOT)) for p in OUT.glob(f'parent_{i}_*_time.txt')]
            files += [f'ntuples/energy_ml_stage131/parent_{i}_selected.npz']
    with tempfile.TemporaryDirectory(prefix='nu_mu_stage131_package_') as tmp:
        with tarfile.open(path,'w:gz') as t:
            for name in dict.fromkeys(files):
                source=ROOT/name
                if phase in ['analysis','audit'] and name.startswith('ntuples/energy_ml_stage131/production_') and not source.is_file():
                    source=Path(tmp)/Path(name).name
                    subprocess.run(['xrdcp','--silent',f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{name}',str(source)],check=True)
                t.add(source,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    worker=SPOOL/f'worker_{stamp}.sh'
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage131.sh').read_bytes())
    descriptor=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} {phase} $(task_index)
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = {cpus}
request_memory = {memory}MB
request_disk = 12000MB
max_retries = 0
+MaxRuntime = 86400
+NuMuStage = "energy-ml-stage131"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue task_index in {','.join(map(str,indices))}
'''
    if phase=='production':
        descriptor=descriptor.replace('queue task_index in','max_materialize = 32\nmax_idle = 32\nqueue task_index in')
    sub=SPOOL/f'{phase}_{stamp}.sub';sub.write_text(descriptor)
    result=subprocess.check_output(['condor_submit','-terse',str(sub)],text=True).strip()
    record=dict(phase=phase,result=result,indices=list(indices),cpus=cpus,
        descriptor=descriptor,package=dict(path=relative,bytes=path.stat().st_size,files=files))
    (OUT/f'{phase}_submission_{stamp}.json').write_text(json.dumps(record,indent=2)+'\n')
    (OUT/f'{phase}_submission.json').write_text(json.dumps(record,indent=2)+'\n')
    print(result)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase');p.add_argument('--indices',nargs='+',type=int,default=[0]);p.add_argument('--cpus',type=int,default=4);p.add_argument('--memory',type=int,default=12000);a=p.parse_args()
    submit(a.phase,a.indices,a.cpus,a.memory)
