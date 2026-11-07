"""Text/stdlib-only immutable packaging and scoped Condor submission."""
import argparse,json,subprocess,tarfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage129_energy_ml';SPOOL=Path('/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage129')
def submit(phase,files,indices=(0,),cpus=4,memory=8000,runtime=7200):
 stamp=time.time_ns()
 relative=f'software/stage129/{stamp}/energy-ml-stage129-{phase}.tar.gz'
 target=ROOT/relative;target.parent.mkdir(parents=True)
 with tarfile.open(target,'w:gz') as t:
  for f in dict.fromkeys(files):t.add(ROOT/f,arcname=f)
 package=dict(files=files,indices=list(indices),bytes=target.stat().st_size,path=relative)
 (OUT/f'{phase}_package.json').write_text(json.dumps(package,indent=2)+'\n')
 SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
 worker=SPOOL/f'worker_{phase}_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage129.sh').read_bytes())
 text=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} {phase} $(source_index)
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/{relative}
should_transfer_files = YES
transfer_output_files = ""
request_cpus = {cpus}
request_memory = {memory}MB
request_disk = 8000MB
max_retries = 0
+MaxRuntime = {runtime}
+NuMuStage = "energy-ml-stage129"
log = {SPOOL}/logs/$(ClusterId).$(ProcId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue source_index in {','.join(map(str,indices))}
'''
 sub=SPOOL/f'{phase}_{stamp}.sub';sub.write_text(text);result=subprocess.check_output(['condor_submit','-terse',str(sub)],text=True)
 record=dict(result=result,descriptor=text,package=package,phase=phase)
 (OUT/f'{phase}_submission.json').write_text(json.dumps(record,indent=2)+'\n')
 (OUT/f'submission_{stamp}.json').write_text(json.dumps(record,indent=2)+'\n');print(result)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase');p.add_argument('manifest');p.add_argument('--indices',nargs='+',type=int,default=[0]);p.add_argument('--cpus',type=int,default=4);p.add_argument('--memory',type=int,default=8000);a=p.parse_args();submit(a.phase,json.loads(Path(a.manifest).read_text()),a.indices,a.cpus,a.memory)
