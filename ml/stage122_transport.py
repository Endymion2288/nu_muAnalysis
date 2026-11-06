"""Standard-library packaging/byte-verified transport; no scientific calculations."""
import argparse
import json
import tarfile
import subprocess
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/'ntuples/energy_ml_stage122'
OUT=ROOT/'workbook/stage122_energy_ml'


def collect(name,replace=False,candidate=False,archive=None):
    archive=Path(archive) if archive else CACHE/f'{name}_result.tar.gz';records=[]
    with tarfile.open(archive) as t:
        for m in t.getmembers():
            if not m.isfile():continue
            part=Path(m.name);assert not part.is_absolute() and '..' not in part.parts
            dest=CACHE/name/part.relative_to('result') if candidate else ROOT/part
            data=t.extractfile(m).read()
            if dest.exists() and not replace:assert dest.read_bytes()==data,str(dest)
            else:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
            assert dest.read_bytes()==data
            records.append(dict(path=str(dest.relative_to(ROOT)),bytes=len(data)))
    (OUT/f'{name}_transport.json').write_text(json.dumps(dict(archive=str(archive),members=records,byte_verified=True),indent=2)+'\n')
    print('Collected',name,len(records),flush=True)


def package(phase,files):
    paths=list(dict.fromkeys(files))
    with tarfile.open(ROOT/f'software/energy-ml-stage122-{phase}.tar.gz','w:gz') as t:
        for f in paths:t.add(ROOT/f,arcname=f)
    (OUT/f'{phase}_package.json').write_text(json.dumps(dict(files=paths),indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--replace',action='store_true');p.add_argument('--candidate',action='store_true');p.add_argument('--archive');p.add_argument('--fetch',action='store_true');a=p.parse_args()
    if a.fetch:
        with tempfile.TemporaryDirectory(prefix='nu_mu_stage122_transport_') as temp:
            archive=Path(temp)/'result.tar.gz'
            subprocess.run(['xrdcp','--silent','--force',f'root://eoshome-x.cern.ch//eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage122/{a.name}_result.tar.gz',str(archive)],check=True)
            collect(a.name,a.replace,a.candidate,archive)
    else:collect(a.name,a.replace,a.candidate,a.archive)
