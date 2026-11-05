"""Local standard-library transport; scientific payload execution is batch-only."""
import argparse
import ast
import json
import shutil
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage119_energy_ml'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage119'


def main(action,phase,result_override=None):
    archive=ROOT/f'software/energy-ml-stage119-{phase}.tar.gz'
    result=Path(result_override) if result_override else ROOT/f'ntuples/energy_ml_stage119/{phase}_result.tar.gz'
    plan=OUT/f'{phase}_package.json'
    if action=='package':
        files=['workbook/stage119_energy_ml/protocol.json',f'ml/stage119_{phase}.py']
        if phase!='probe':files += json.loads((OUT/f'{phase}_inputs.json').read_text())
        files=list(dict.fromkeys(files))
        for n in files:
            assert (ROOT/n).is_file(),n
            if n.endswith('.py'):ast.parse((ROOT/n).read_text())
        with tarfile.open(archive,'w:gz',compresslevel=1) as t:
            for n in files:t.add(ROOT/n,arcname=n)
        SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
        worker=SPOOL/f'worker_{phase}.sh'
        # A running bash reads this file incrementally. Never rewrite a shared
        # worker when packaging a different concurrent phase.
        payload=(ROOT/'AnalysisZipFramework/submission/run_ml_stage119.sh').read_bytes()
        if worker.exists():assert worker.read_bytes()==payload, f'Use a new phase for changed worker: {phase}'
        else:worker.write_bytes(payload)
        plan.write_text(json.dumps(dict(files=files,archive_bytes=archive.stat().st_size,
            input_bytes=sum((ROOT/n).stat().st_size for n in files),local_numerics=False),indent=2)+'\n')
        print('packaged',phase,archive.stat().st_size)
    else:
        record=json.loads(plan.read_text())
        with tarfile.open(archive) as t:
            for n in record['files']:assert t.extractfile(n).read()==(ROOT/n).read_bytes(),n
        with tarfile.open(result) as t:
            for member in t.getmembers():
                if not member.isfile():continue
                p=Path(member.name);assert not p.is_absolute() and '..' not in p.parts
                assert p.parts[:2] in [('workbook','stage119_energy_ml'),('ntuples','energy_ml_stage119')] or p.parts[:3]==('ml','artifacts','stage119')
                payload=t.extractfile(member).read();dest=ROOT/p;dest.parent.mkdir(parents=True,exist_ok=True)
                if dest.exists():assert dest.read_bytes()==payload,str(p)
                else:dest.write_bytes(payload)
        (OUT/f'{phase}_transport.json').write_text(json.dumps(dict(passed=True,input_files=len(record['files']),result_bytes=result.stat().st_size,local_numerics=False),indent=2)+'\n')
        print('collected',phase)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['package','collect']);p.add_argument('phase')
    p.add_argument('--result',help='Explicit locally transported result, e.g. while EOS mount metadata is stale')
    a=p.parse_args();main(a.action,a.phase,a.result)
