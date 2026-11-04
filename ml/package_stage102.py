"""Stage102 standard-library-only packaging and immutable result collection."""
import argparse
import ast
import json
import shutil
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO/'workbook/stage102_energy_ml'
SPOOL = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage102')


def closure(entries):
    found, pending = set(), list(entries)
    while pending:
        name = pending.pop()
        if name in found:
            continue
        found.add(name)
        for node in ast.walk(ast.parse((REPO/name).read_text())):
            imports = [node.module] if isinstance(node, ast.ImportFrom) else [n.name for n in node.names] if isinstance(node, ast.Import) else []
            for module in imports:
                if module:
                    path = 'ml/'+module.split('.')[0]+'.py'
                    if (REPO/path).exists() and path not in found:
                        pending.append(path)
    return sorted(found)


def package(mode):
    if mode == 'fit':
        assert json.loads((OUT/'admission.json').read_text())['passed']
        assert not (OUT/'fit_started.json').exists()
        assert not (REPO/'ml/artifacts/stage102/P.pt').exists()
    code = closure([f'ml/stage102_{mode}.py', 'ml/stage102_common.py'])
    files = code+['ml/configs/audited_features.json',
        'workbook/stage101_energy_ml/stage102_contract.json',
        'workbook/stage94_energy_ml/preprocessing.json',
        'workbook/stage94_energy_ml/X_calo_groups.json',
        'workbook/stage94_energy_ml/X_activity_groups.json',
        'workbook/stage94_energy_ml/offsets.tsv',
        'workbook/stage87_energy_ml/protocol.json',
        'workbook/stage87_energy_ml/normalization.json',
        'ntuples/energy_ml_stage94/cal_partition.npz',
        'ntuples/energy_ml_stage87/split.npz']
    if mode in ['qa', 'fit']:
        files += ['ntuples/energy_ml_stage55/dataset.npz', 'ntuples/energy_ml_stage56/readout.npz']
        files += [f'ntuples/energy_ml_stage{s}/support.npz' for s in [70, 81, 82, 83]]
        files += ['ml/artifacts/stage87/predictions.npz', 'ntuples/energy_ml_stage90/input.npz',
                  'ml/artifacts/stage94/E_2026110494.pt', 'ml/artifacts/stage94/point_predictions.npz']
    else:
        files += ['ntuples/energy_ml_stage94/evaluation_input.npz',
                  'ml/artifacts/stage87/predictions.npz',
                  'ml/artifacts/stage94/point_predictions.npz',
                  'workbook/stage94_energy_ml/metrics.tsv',
                  'ml/artifacts/stage102/heads.npz']
    files += [str(p.relative_to(REPO)) for p in sorted(OUT.glob('*.json'))]
    archive = REPO/f'software/energy-ml-stage102-{mode}.tar.gz'
    with tarfile.open(archive, 'w:gz', compresslevel=1) as tar:
        for name in dict.fromkeys(files):
            tar.add(REPO/name, arcname=name)
    SPOOL.mkdir(exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    shutil.copyfile(REPO/'AnalysisZipFramework/submission/run_ml_stage102.sh', SPOOL/'worker.sh')
    print(json.dumps(dict(mode=mode, bytes=archive.stat().st_size, files=len(set(files)),
                         numerical_work_local=False)), flush=True)


def collect(mode, archive):
    with tarfile.open(archive or REPO/f'ntuples/energy_ml_stage102/result_{mode}.tar.gz') as tar:
        for m in tar.getmembers():
            if not m.isfile():
                continue
            path = Path(m.name)
            assert not path.is_absolute() and '..' not in path.parts
            assert path.parts[:2] in [('workbook', 'stage102_energy_ml'),
                                     ('ntuples', 'energy_ml_stage102')] or path.parts[:3] == ('ml', 'artifacts', 'stage102')
            dest = REPO/path
            value = tar.extractfile(m).read()
            if dest.exists():
                assert dest.read_bytes() == value, dest
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(value)
    with tarfile.open(REPO/f'software/energy-ml-stage102-{mode}.tar.gz') as tar:
        for m in tar.getmembers():
            if m.isfile() and m.name.startswith(('ntuples/', 'ml/artifacts/')) and 'stage102/' not in m.name:
                assert tar.extractfile(m).read() == (REPO/m.name).read_bytes(), m.name
    print(mode+': collected; original packaged cache/model inputs byte-identical')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['package', 'collect'])
    p.add_argument('mode', choices=['qa', 'fit', 'report'])
    p.add_argument('--archive')
    a = p.parse_args()
    if a.action == 'package':
        package(a.mode)
    else:
        collect(a.mode, a.archive)
