"""Standard-library packaging/collection; no local event or model evaluation."""
import argparse
import ast
import json
import shutil
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage115_energy_ml'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage115'
PACKAGE=ROOT/'software/energy-ml-stage115.tar.gz'
RESULT=ROOT/'ntuples/energy_ml_stage115/result.tar.gz'
FILES=['ml/stage115_run.py','ml/stage115_common.py','ml/stage115_head.py','ml/stage115_report.py',
       'ml/stage115_supervise.py','ml/stage113_supervise.py','ml/audited_features.py',
       'ml/configs/audited_features.json','ntuples/energy_ml_stage94/evaluation_input.npz',
       'ntuples/energy_ml_stage94/cal_partition.npz','ntuples/energy_ml_stage87/split.npz',
       'ml/artifacts/stage87/predictions.npz','ntuples/energy_ml_stage55/dataset.npz',
       'ntuples/energy_ml_stage56/readout.npz']
FILES += [f'ntuples/energy_ml_stage{s}/support.npz' for s in [70,81,82,83]]
FILES += ['workbook/stage87_energy_ml/protocol.json','workbook/stage94_energy_ml/metrics.tsv',
          'workbook/stage115_energy_ml/protocol.json']


def package():
    assert not (OUT/'submission.json').exists()
    for name in FILES:
        assert (ROOT/name).is_file(),name
        if name.endswith('.py'):ast.parse((ROOT/name).read_text())
    with tarfile.open(PACKAGE,'w:gz',compresslevel=1) as t:
        for name in FILES:t.add(ROOT/name,arcname=name)
    SPOOL.mkdir(parents=True,exist_ok=True);(SPOOL/'logs').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'AnalysisZipFramework/submission/run_ml_stage115.sh',SPOOL/'worker.sh')
    RESULT.parent.mkdir(exist_ok=True)
    (OUT/'package.json').write_text(json.dumps(dict(files=FILES,files_count=len(FILES),archive_bytes=PACKAGE.stat().st_size,
        logical_input_bytes=sum((ROOT/n).stat().st_size for n in FILES),spool=str(SPOOL),local_event_or_model_execution=False),indent=2)+'\n')
    print('Packaged',len(FILES),'files;',PACKAGE.stat().st_size,'bytes')


def collect():
    with tarfile.open(RESULT) as t:
        for member in t.getmembers():
            if not member.isfile():continue
            p=Path(member.name)
            assert not p.is_absolute() and '..' not in p.parts
            assert p.parts[:2]==('workbook','stage115_energy_ml') or p.parts[:3]==('ml','artifacts','stage115')
            dest=ROOT/p;content=t.extractfile(member).read();dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():assert dest.read_bytes()==content,str(p)
            else:dest.write_bytes(content)
    with tarfile.open(PACKAGE) as t:
        for name in FILES:assert t.extractfile(name).read()==(ROOT/name).read_bytes(),name
    (OUT/'transport_validation.json').write_text(json.dumps(dict(passed=True,byte_exact_input_files=len(FILES),
        result_bytes=RESULT.stat().st_size,local_numerical_execution=False),indent=2)+'\n')
    print('Collected; all input bytes unchanged')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['package','collect']);a=p.parse_args()
    package() if a.action=='package' else collect()
