"""Standard-library packaging/collection; no local numerical execution."""
import argparse
import ast
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage104_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage104'
PACKAGE = ROOT/'software/energy-ml-stage104.tar.gz'
RESULT = ROOT/'ntuples/energy_ml_stage104/result.tar.gz'


def sources():
    found, pending = set(), ['ml/stage104_decision.py']
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
    assert not (OUT/'optimization_started.json').exists()
    files = sources()+[
        'ntuples/energy_ml_stage94/evaluation_input.npz',
        'ntuples/energy_ml_stage94/cal_partition.npz',
        'ml/artifacts/stage94/point_predictions.npz',
        'ml/artifacts/stage94/MDN_heads.npz',
        'ml/artifacts/stage87/predictions.npz',
        'workbook/stage94_energy_ml/metrics.tsv',
        'workbook/stage99_energy_ml/calibration.json',
        'workbook/stage104_energy_ml/protocol.json']
    with tarfile.open(PACKAGE, 'w:gz', compresslevel=1) as tar:
        for name in files:
            tar.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'AnalysisZipFramework/submission/run_ml_stage104.sh', SPOOL/'worker.sh')
    RESULT.parent.mkdir(exist_ok=True)
    print(json.dumps(dict(files=len(files), bytes=PACKAGE.stat().st_size, spool=str(SPOOL), local_numerical_work=False)))


def collect(archive):
    with tarfile.open(archive or RESULT) as tar:
        for m in tar.getmembers():
            if not m.isfile():
                continue
            path = Path(m.name)
            assert not path.is_absolute() and '..' not in path.parts
            assert path.parts[:2] in [('workbook', 'stage104_energy_ml'), ('ntuples', 'energy_ml_stage104')]
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
    (OUT/'packaging_validation.json').write_text(json.dumps(dict(passed=True, byte_identical_files=checked), indent=2)+'\n')
    print('collected; source and original inputs byte-identical')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['package', 'collect'])
    parser.add_argument('--archive')
    args = parser.parse_args()
    package() if args.action == 'package' else collect(args.archive)
