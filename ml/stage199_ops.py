"""Immutable source packages and current-state scheduling for the all-flux experiment."""
import argparse
import json
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage199_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage199'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage199'


def submit(phase):
    assert not (OUT/f'{phase}_submission.json').exists()
    protocol=json.loads((OUT/'protocol.json').read_text())
    if phase=='pilot':indices=protocol['pilot_indices']
    else:
        assert json.loads((OUT/'pilot_admission.json').read_text())['passed']
        indices=[s['index'] for s in protocol['sources'] if s['mode']!='cache130'
                 and not (s['mode']=='local' and s['index'] in protocol['pilot_indices'])]
    stamp=time.time_ns();relative=Path(f'software/stage199/{stamp}/energy-ml-stage199.tar.gz')
    package=ROOT/relative;package.parent.mkdir(parents=True)
    files=[str(p.relative_to(ROOT)) for p in (ROOT/'ml').glob('*.py')]
    files+=['ml/configs','AnalysisZipFramework/config','build/analysis','setup_env.sh',
            'workbook/stage199_energy_ml/protocol.json','workbook/stage130_energy_ml/payload_snapshot.json',
            'AnalysisZipFramework/submission/run_ml_stage199_source.sh']
    with tarfile.open(package,'w:gz') as a:
        for name in files:a.add(ROOT/name,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
    worker=SPOOL/f'worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage199_batch.sh').read_bytes())
    batches=[indices[i:i+8] for i in range(0,len(indices),8)]
    queue='\n'.join(','.join(map(str,b)) for b in batches)
    descriptor=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} {phase} $(indices)
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 8
request_memory = 24000MB
request_disk = 50000MB
max_retries = 0
max_materialize = 20
max_idle = 20
+MaxRuntime = 172800
+NuMuStage = "energy-ml-stage199"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue indices from (
{queue}
)
'''
    path=SPOOL/f'{phase}_{stamp}.sub';path.write_text(descriptor)
    result=subprocess.check_output(['condor_submit','-terse',str(path)],text=True).strip()
    (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(result=result,phase=phase,batches=batches,
        indices=indices,package=str(relative),descriptor=descriptor),indent=2)+'\n')
    print(result,flush=True)


def collect(phase):
    sub=json.loads((OUT/f'{phase}_submission.json').read_text())
    listing=subprocess.check_output(['xrdfs','root://eoshome-x.cern.ch','ls',
        '/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage199'],text=True)
    present={Path(line).name for line in listing.splitlines()}
    rows=[]
    for index in sub['indices']:
        archive=CACHE/f'{phase}_{index}.tar.gz'
        if archive.name not in present:
            rows.append(dict(index=index,state='not_returned'));continue
        destination=CACHE/f'{phase}_{index}'
        if not (destination/'exitcode.txt').exists():
            destination.mkdir(exist_ok=True)
            with tempfile.NamedTemporaryFile(suffix='.tar.gz') as tmp:
                subprocess.run(['xrdcp','--silent','--force',f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage199/{archive.name}',tmp.name],check=True)
                with tarfile.open(tmp.name) as a:
                    for m in a.getmembers():
                        if not m.isfile():continue
                        assert m.name.startswith('result/') and '..' not in m.name
                        p=destination/Path(m.name).relative_to('result');p.write_bytes(a.extractfile(m).read())
        rc=int((destination/'exitcode.txt').read_text())
        rows.append(dict(index=index,state='success' if rc==0 else 'failed',exitcode=rc))
    summary=dict(rows=rows,returned=sum(r['state']!='not_returned' for r in rows),
                 success=sum(r['state']=='success' for r in rows),failed=[r['index'] for r in rows if r['state']=='failed'])
    (OUT/f'{phase}_collection.json').write_text(json.dumps(summary,indent=2)+'\n')
    print({k:v for k,v in summary.items() if k!='rows'},flush=True)


def science(phase, platform='condor', attempt=0):
    assert not (OUT/f'{phase}_submission.json').exists(), 'Phase already submitted; inspect its actual state before any repair'
    stamp=time.time_ns()
    relative=Path(f'software/stage199/{stamp}/energy-ml-stage199-science.tar.gz')
    path=ROOT/relative;path.parent.mkdir(parents=True)
    files=[str(p.relative_to(ROOT)) for p in (ROOT/'ml').glob('*.py')]
    files+=['ml/configs','workbook/stage199_energy_ml/protocol.json',
            'workbook/stage158_energy_ml/preexisting_asset_snapshot.json',
            'workbook/stage199_energy_ml/prefit_split_clarification.json']
    if (OUT/'prepare.json').exists():files.append('workbook/stage199_energy_ml/prepare.json')
    if (OUT/'fit.json').exists():files+=['workbook/stage199_energy_ml/fit.json','workbook/stage199_energy_ml/platform.json']
    if (OUT/'decisions.json').exists():files+=['workbook/stage199_energy_ml/decisions.json','workbook/stage199_energy_ml/metrics.tsv','workbook/stage199_energy_ml/paired.tsv']
    with tarfile.open(path,'w:gz') as a:
        for name in files:a.add(ROOT/name,arcname=name)
        a.add('/usr/bin/time',arcname='runtime/bin/time')
    worker=SPOOL/f'science_{stamp}.sh';worker.parent.mkdir(parents=True,exist_ok=True)
    worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage199_science.sh').read_bytes())
    if platform=='kubeflow':
        # Both worker and package are immutable per submission.
        shared=ROOT/f'software/stage199/{stamp}/worker.sh';shared.write_bytes(worker.read_bytes())
        suffix=f'-r{attempt}' if attempt else ''
        job_name=f'nu-mu-energy-stage199-{phase}{suffix}'
        job=dict(apiVersion='batch/v1',kind='Job',metadata=dict(name=job_name,namespace='xcheng',labels={'analysis-stage':'nu-mu-energy-199'}),
            spec=dict(backoffLimit=0,activeDeadlineSeconds=7200,template=dict(metadata=dict(labels={'mount-eos':'true','mount-cvmfs':'true','home':'eos'}),
                spec=dict(serviceAccountName='default-editor',restartPolicy='Never',nodeSelector={'nvidia.com/gpu.product':'NVIDIA-H100-NVL'},
                    containers=[dict(name=phase,image='registry.cern.ch/mlops/lxplus-like:9',imagePullPolicy='IfNotPresent',
                        command=['bash','-lc'],args=[f'bash /eos/user/x/xcheng/FASER/nu_muAnalysis/{shared.relative_to(ROOT)} {phase} /eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}'],
                        resources=dict(requests={'cpu':'8','memory':'16Gi'},limits={'cpu':'8','memory':'24Gi','nvidia.com/mig-3g.47gb':1}))]))))
        if phase!='fit':
            spec=job['spec']['template']['spec'];spec.pop('nodeSelector')
            spec['containers'][0]['resources']=dict(requests={'cpu':'2','memory':'6Gi'},limits={'cpu':'8','memory':'12Gi'})
        else:
            # CERN GPU admission assigns CPU/memory from the accelerator profile.
            job['spec']['template']['spec']['containers'][0]['resources']=dict(limits={'nvidia.com/mig-3g.47gb':1})
        descriptor=ROOT/f'AnalysisZipFramework/submission/ml_stage199_{phase}{suffix}_kubeflow.json';descriptor.write_text(json.dumps(job,indent=2)+'\n')
        result=subprocess.check_output(['kubectl','create','-f',str(descriptor)],text=True).strip()
    else:
        descriptor=SPOOL/f'{phase}_{stamp}.sub'
        memory_MB=12000 if phase=='prepare' else 24000
        text=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} {phase} energy-ml-stage199-science.tar.gz
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = 8
request_memory = {memory_MB}MB
request_disk = 5000MB
max_retries = 0
+MaxRuntime = 86400
+NuMuStage = "energy-ml-stage199"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue 1
'''
        descriptor.write_text(text)
        result=subprocess.check_output(['condor_submit','-terse',str(descriptor)],text=True).strip()
    (OUT/f'{phase}_submission.json').write_text(json.dumps(dict(result=result,phase=phase,platform=platform,
        attempt=attempt,job_name=job_name if platform=='kubeflow' else None,
        package=str(relative),descriptor=str(descriptor),worker=str(worker)),indent=2)+'\n')
    print(result,flush=True)


def science_collect(phase):
    archive=CACHE/f'{phase}_result.tar.gz'
    with tempfile.NamedTemporaryFile(suffix='.tar.gz') as tmp:
        subprocess.run(['xrdcp','--silent','--force',f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage199/{archive.name}',tmp.name],check=True)
        with tarfile.open(tmp.name) as a:
            for m in a.getmembers():
                if not m.isfile():continue
                assert m.name.startswith(('workbook/stage199_energy_ml/','ntuples/energy_ml_stage199/','ml/artifacts/stage199/')) and '..' not in m.name
                target=ROOT/m.name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(a.extractfile(m).read())
    print('collected',phase,(OUT/f'{phase}_exitcode.txt').read_text().strip())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['submit','collect','science','science_collect']);p.add_argument('phase',choices=['pilot','production','prepare','fit','report','audit']);p.add_argument('--platform',default='condor',choices=['condor','kubeflow']);p.add_argument('--attempt',type=int,default=0);a=p.parse_args()
    if a.action=='science':science(a.phase,a.platform,a.attempt)
    else:globals()[a.action](a.phase)
