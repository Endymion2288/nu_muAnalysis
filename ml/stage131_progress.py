"""Transactionally collect completed batches and track every fixed parent."""
import fcntl
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from stage131_common import ROOT,OUT,CACHE,protocol

def main():
    p=protocol();transport_pending=[]
    listed={f.name for f in CACHE.glob('production_*_result.tar.gz')}
    for index in range(len(p['batches'])):
        archive=CACHE/f'production_{index}_result.tar.gz';audit=OUT/f'production_{index}_transfer.json'
        if archive.name not in listed:continue
        if audit.exists() and 'parents' in json.loads(audit.read_text()):continue
        command=[sys.executable,str(ROOT/'ml/stage131_collect.py'),'production',str(index)]
        # eosxd may list a new remote result while a previous negative stat is
        # cached. Fetch that exact completed return through XRootD, never rerun
        # the physics or overwrite the remote archive to refresh its metadata.
        with tempfile.TemporaryDirectory(prefix='nu_mu_stage131_collect_') as tmp:
            if not archive.is_file():
                local=Path(tmp)/archive.name
                fetch=subprocess.run(['xrdcp','--silent',f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage131/{archive.name}',str(local)],capture_output=True,text=True)
                if fetch.returncode:
                    transport_pending.append(dict(batch=index,message=fetch.stderr[-250:]));continue
                command+=['--archive',str(local)]
            result=subprocess.run(command,capture_output=True,text=True)
        if result.returncode:transport_pending.append(dict(batch=index,message=result.stderr[-250:]))
    completed=[];failed=[];selected=0;inventory={}
    for audit in OUT.glob('production_*_transfer.json'):
        r=json.loads(audit.read_text())
        for parent in r.get('parents',[]):inventory[parent['index']]=parent
    for i in p['indices']:
        if i in inventory:
            r=inventory[i]
            if r['successful']:completed.append(i);selected+=r['selected_N']
            else:failed.append(i)
            continue
        summary=OUT/f'parent_{i}_summary.json'
        if not summary.exists():continue
        r=json.loads(summary.read_text())
        if r.get('successful'):
            assert (CACHE/f'parent_{i}_selected.npz').is_file()
            completed.append(i);selected+=json.loads((OUT/f'parent_{i}_selection.json').read_text())['selected_N']
        else:failed.append(i)
    result=dict(frozen_parents=p['parents_N'],completed=len(completed),pending=p['parents_N']-len(completed)-len(failed),failed=failed,reselected=selected,all_responses_complete=len(completed)==p['parents_N'],transport_pending=transport_pending,scope='conditional replay yield; no newly independentneutrino count, no energy fit beforeallresponses')
    (OUT/'production_progress.json').write_text(json.dumps(result,indent=2)+'\n');print(result)

if __name__=='__main__':
    with (CACHE/'.collector.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);main()
