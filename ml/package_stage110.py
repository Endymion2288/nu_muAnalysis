"""Standard-library transport and source checks; numerical execution stays in batch."""
import argparse
import ast
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage110_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage110'
PACKAGE = ROOT/'software/energy-ml-stage110.tar.gz'
RESULT = ROOT/'ntuples/energy_ml_stage110/result.tar.gz'


def sources():
    found, pending = set(), ['ml/stage110_transfer.py', 'ml/stage110_solver.py']
    while pending:
        name = pending.pop()
        if name in found:
            continue
        found.add(name)
        for node in ast.walk(ast.parse((ROOT/name).read_text())):
            modules = [node.module] if isinstance(node, ast.ImportFrom) else [v.name for v in node.names] if isinstance(node, ast.Import) else []
            for module in modules:
                path = 'ml/'+module.split('.')[0]+'.py' if module else ''
                if path and (ROOT/path).exists() and path not in found:
                    pending.append(path)
    return sorted(found)


def package():
    assert not (OUT/'selection.json').exists()
    files = sources()+[
        'ntuples/energy_ml_stage94/evaluation_input.npz',
        'ntuples/energy_ml_stage94/cal_partition.npz',
        'ntuples/energy_ml_stage87/split.npz',
        'ml/artifacts/stage108/predictions.npz',
        'ml/artifacts/stage87/predictions.npz',
        'workbook/stage94_energy_ml/metrics.tsv',
        'workbook/stage110_energy_ml/protocol.json']
    with tarfile.open(PACKAGE, 'w:gz', compresslevel=1) as tar:
        for name in files:
            tar.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'AnalysisZipFramework/submission/run_ml_stage110.sh', SPOOL/'worker.sh')
    RESULT.parent.mkdir(exist_ok=True)
    record = dict(files=files, files_count=len(files), archive_bytes=PACKAGE.stat().st_size,
                  spool=str(SPOOL), local_numerical_work=False)
    (OUT/'package.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record, indent=2))


def collect():
    with tarfile.open(RESULT) as tar:
        for m in tar.getmembers():
            if not m.isfile():
                continue
            path = Path(m.name)
            assert not path.is_absolute() and '..' not in path.parts
            assert path.parts[:2] in [('workbook', 'stage110_energy_ml'), ('ntuples', 'energy_ml_stage110')]
            dest = ROOT/path
            content = tar.extractfile(m).read()
            if dest.exists():
                assert dest.read_bytes() == content, dest
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
    checked = []
    with tarfile.open(PACKAGE) as tar:
        for m in tar.getmembers():
            if m.isfile():
                assert tar.extractfile(m).read() == (ROOT/m.name).read_bytes(), m.name
                checked.append(m.name)
    (OUT/'transport_validation.json').write_text(json.dumps(dict(passed=True,
        original_byte_identical_files=checked, result_bytes=RESULT.stat().st_size,
        no_local_numerical_execution=True), indent=2)+'\n')
    print('collected; source and original inputs byte-identical')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['package', 'collect'])
    a = p.parse_args()
    package() if a.action == 'package' else collect()
