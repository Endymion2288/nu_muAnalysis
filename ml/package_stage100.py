"""Package/collect Stage100 with stdlib only; no local numerical work."""
import argparse
import ast
import json
import shutil
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO/'workbook/stage100_energy_ml'
BASE = ['ntuples/energy_ml_stage55/dataset.npz', 'ntuples/energy_ml_stage56/readout.npz'] + [
    f'ntuples/energy_ml_stage{s}/support.npz' for s in [70, 81, 82, 83]]
OLD = ['ntuples/energy_ml_stage95/cohort.json', 'ntuples/energy_ml_stage87/split.npz',
       'ml/artifacts/stage99/B_classifier_B.json'] + [
    f'ntuples/energy_ml_stage99/{n}.tsv' for n in ['B_identities', 'B_collection_features', 'B_classifier_predictions']]
EVIDENCE = ['workbook/stage99_energy_ml/'+n for n in
            ['B_classifier_metrics.tsv', 'B_classifier_ROC_working.tsv', 'B_class_support.tsv']]


def package(mode):
    if mode == 'fit':
        assert json.loads((OUT/'QA.json').read_text())['passed']
        assert not (OUT/'fit_started.json').exists(), 'The sole fit attempt has already started'
        assert not (REPO/'ntuples/energy_ml_stage100/predictions.tsv').exists()
    code = ['ml/audited_features.py', 'ml/configs/audited_features.json']
    code += [str(p.relative_to(REPO)) for p in sorted((REPO/'ml').glob('stage100_*.py'))]
    for name in code:
        if name.endswith('.py'):
            ast.parse((REPO/name).read_text())
    metadata = [str(p.relative_to(REPO)) for p in sorted(OUT.glob('*.json'))]
    files = sorted(set(code+BASE+OLD+EVIDENCE+metadata))
    if mode in ['validate', 'audit']:
        files += ['ntuples/energy_ml_stage100/predictions.tsv',
                  'ntuples/energy_ml_stage100/train_predictions.tsv',
                  'ml/artifacts/stage100/A_classifier.json']
        files += [str(p.relative_to(REPO)) for p in sorted(OUT.glob('*.tsv'))]
    archive = REPO/f'software/energy-ml-stage100-{mode}.tar.gz'
    with tarfile.open(archive, 'w:gz', compresslevel=1) as tar:
        for name in dict.fromkeys(files):
            tar.add(REPO/name, arcname=name)
    spool = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage100')
    (spool/'logs').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO/'AnalysisZipFramework/submission/run_ml_stage100.sh', spool/'worker.sh')
    print(json.dumps(dict(mode=mode, archive_bytes=archive.stat().st_size, files=len(set(files)), local_fits=0)))


def collect(mode, archive=None):
    archive = Path(archive) if archive else REPO/f'ntuples/energy_ml_stage100/result_{mode}.tar.gz'
    with tarfile.open(archive) as tar:
        for m in tar.getmembers():
            if not m.isfile():
                continue
            path = Path(m.name)
            assert not path.is_absolute() and '..' not in path.parts
            dest = REPO/path
            if mode == 'qa' and path.as_posix() == 'workbook/stage100_energy_ml/protocol.json':
                dest = OUT/'protocol_QA.json'
            value = tar.extractfile(m).read()
            if dest.exists():
                assert dest.read_bytes() == value, dest
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(value)
    # B inputs must remain byte-identical to the input package.
    with tarfile.open(REPO/f'software/energy-ml-stage100-{mode}.tar.gz') as tar:
        for name in OLD:
            assert tar.extractfile(name).read() == (REPO/name).read_bytes(), name
    print(mode+': collected; original B/cohort inputs byte-identical')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['package', 'collect'])
    parser.add_argument('mode', choices=['qa', 'fit', 'validate', 'audit'])
    parser.add_argument('--archive', help='Local transfer fallback when the EOS mount listing is stale')
    a = parser.parse_args()
    if a.action == 'package':
        package(a.mode)
    else:
        collect(a.mode, a.archive)
