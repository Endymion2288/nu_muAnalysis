"""Collect a known Stage96 return archive, preserving frozen preexisting artifacts."""
import argparse
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
OUT=REPO/'workbook/stage96_energy_ml'


def main(mode,cluster):
    if cluster:
        p=subprocess.run(['condor_history',str(cluster),'-limit','1','-json'],capture_output=True,text=True,check=True)
        history=json.loads(p.stdout);assert len(history)==1 and history[0]['ExitCode']==0
        (OUT/(mode+'_history.json')).write_text(json.dumps(history,indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='stage96_return_') as d:
        archive=Path(d)/'return.tar.gz'
        remote=f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage96/result_{mode}.tar.gz'
        subprocess.run(['xrdcp','--silent',remote,str(archive)],check=True)
        existing=[];added=[]
        with tarfile.open(archive) as t:
            for item in t.getmembers():
                p=Path(item.name)
                assert not p.is_absolute() and '..' not in p.parts
                assert any(p==Path(base) or Path(base) in p.parents for base in ['workbook/stage96_energy_ml','ntuples/energy_ml_stage96','ml/artifacts/stage96'])
                if item.isdir():continue
                assert item.isfile()
                target=REPO/p;data=t.extractfile(item).read()
                if target.exists():
                    assert target.read_bytes()==data,str(p)
                    existing.append(str(p))
                else:
                    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);added.append(str(p))
        result=dict(passed=True,mode=mode,archive_bytes=archive.stat().st_size,existing_byte_equal=existing,new_files=added)
        (OUT/(mode+'_collection.json')).write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(mode=mode,matched=len(existing),new_files=len(added))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['extract','fit','report']);p.add_argument('--cluster',type=int)
    a=p.parse_args();main(a.mode,a.cluster)
