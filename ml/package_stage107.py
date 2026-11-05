"""Standard-library transport only. No local numerical or event execution."""
import argparse
import ast
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage107_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage107'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage107'
MODES=['qa_extract','qa']


def package(mode):
    codes=subprocess.check_output(['git','ls-files','ml/*.py']).decode().splitlines()
    codes+=['ml/stage107_device_data.py','ml/stage107_qa.py','ml/time_stage107.py','ml/stage107_extract.py']
    codes=list(dict.fromkeys(codes))
    for name in codes:ast.parse((ROOT/name).read_text())
    files=codes+['ml/configs/audited_features.json','workbook/stage105_energy_ml/protocol.json',
      'workbook/stage105_energy_ml/identities.json','workbook/stage96_energy_ml/sources.json',
      'workbook/stage87_energy_ml/protocol.json','workbook/stage87_energy_ml/normalization.json',
      'workbook/stage94_energy_ml/preprocessing.json',
      'workbook/stage106_energy_ml/QA_extraction.json']
    if mode=='qa':
        files+=['ntuples/energy_ml_stage55/dataset.npz','ntuples/energy_ml_stage56/readout.npz']
        files += [f'ntuples/energy_ml_stage{s}/support.npz' for s in [70,81,82,83]]
        files+=['ntuples/energy_ml_stage87/split.npz','ntuples/energy_ml_stage94/cal_partition.npz']
        files+=['ntuples/energy_ml_stage107/QA_coordinates.npz']
    files += [str(p.relative_to(ROOT)) for p in OUT.glob('*.json')]
    path=ROOT/f'software/energy-ml-stage107-{mode}.tar.gz'
    files=list(dict.fromkeys(files))
    with tarfile.open(path,'w:gz',compresslevel=1) as tar:
        for name in files:tar.add(ROOT/name,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'AnalysisZipFramework/submission/run_ml_stage107.sh',SPOOL/'worker.sh')
    # Record metadata outside the worker package, avoiding circular bytes accounting.
    (OUT/f'package_{mode}.json').write_text(json.dumps(dict(files=files,archive_bytes=path.stat().st_size,local_numerical_work=False),indent=2)+'\n')
    print(mode,'package bytes',path.stat().st_size)


def collect(mode):
    archive=CACHE/f'result_{mode}.tar.gz'
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if not member.isfile():continue
            rel=Path(member.name)
            assert not rel.is_absolute() and '..' not in rel.parts
            assert rel.parts[:2] in [('workbook','stage107_energy_ml'),('ntuples','energy_ml_stage107')] or rel.parts[:3]==('ml','artifacts','stage107')
            dest=ROOT/rel;content=tar.extractfile(member).read()
            if dest.exists():assert dest.read_bytes()==content,rel
            else:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
    packagepath=ROOT/f'software/energy-ml-stage107-{mode}.tar.gz'
    checked=0
    with tarfile.open(packagepath) as tar:
        for member in tar.getmembers():
            if member.isfile():
                assert tar.extractfile(member).read()==(ROOT/member.name).read_bytes(),member.name
                checked+=1
    (OUT/f'collection_{mode}.json').write_text(json.dumps(dict(passed=True,original_input_files_byte_exact=checked,local_numerical_work=False),indent=2)+'\n')
    print('collected',mode,'checked',checked)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['package','collect']);p.add_argument('mode',choices=MODES);a=p.parse_args()
    package(a.mode) if a.action=='package' else collect(a.mode)
