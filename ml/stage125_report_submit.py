"""Package and submit scientific aggregation/figures, or recover their compact outputs."""
import argparse
import json
import subprocess
import tarfile
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage125_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage125'
SPOOL=Path('/afs/cern.ch/user/x/xcheng/condor/nu_muAnalysis/stage125')


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['preview','evaluate','plot']);p.add_argument('--collect',action='store_true');p.add_argument('--archive',type=Path,help='Downloaded archive when the EOS mount has stale metadata');a=p.parse_args()
    if a.collect:
        record=[]
        with tarfile.open(a.archive or CACHE/f'{a.phase}_result.tar.gz') as t:
            for m in t.getmembers():
                path=Path(m.name)
                if not m.isfile():continue
                assert not path.is_absolute() and '..' not in path.parts
                assert m.name.startswith(('workbook/stage125_energy_ml/','ntuples/energy_ml_stage125/'))
                # Preserve the local frozen protocol and submission ledgers.
                if path.name=='protocol.json':continue
                target=ROOT/path;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(t.extractfile(m).read());record.append(dict(path=m.name,bytes=m.size))
        (OUT/f'{a.phase}_transfer.json').write_text(json.dumps(record,indent=2)+'\n');print('Recovered',len(record),'files');return
    package=ROOT/'software/energy-ml-stage125-report.tar.gz'
    with tarfile.open(package,'w:gz') as t:
        for f in sorted((ROOT/'ml').glob('*.py')):t.add(f,arcname=str(f.relative_to(ROOT)))
        for f in ['ml/configs/audited_features.json','workbook/stage125_energy_ml/protocol.json']:t.add(ROOT/f,arcname=f)
    stamp=time.time_ns();worker=SPOOL/f'report_worker_{stamp}.sh';worker.write_bytes((ROOT/'AnalysisZipFramework/submission/run_ml_stage125_report.sh').read_bytes())
    cpus=4
    memory=6000
    desc=f'''universe = vanilla
initialdir = {SPOOL}
executable = /bin/bash
transfer_executable = False
arguments = {worker} {a.phase}
transfer_input_files = root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/software/energy-ml-stage125-report.tar.gz
should_transfer_files = YES
transfer_output_files = ""
request_cpus = {cpus}
request_memory = {memory}MB
request_disk = 2000MB
max_retries = 0
+MaxRuntime = 7200
+NuMuStage = "energy-ml-stage125"
log = {SPOOL}/logs/$(ClusterId).log
output = {SPOOL}/logs/$(ClusterId).$(ProcId).out
error = {SPOOL}/logs/$(ClusterId).$(ProcId).err
queue
'''
    path=SPOOL/f'{a.phase}_{stamp}.sub';path.write_text(desc);result=subprocess.check_output(['condor_submit','-terse',str(path)],text=True)
    (OUT/f'{a.phase}_submission_{stamp}.json').write_text(json.dumps(dict(result=result,descriptor=desc),indent=2)+'\n');print(result)


if __name__=='__main__':main()
