"""Standard-library transport and byte comparison; no local event calculations."""
import argparse
import ast
import csv
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage105_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage105'
PACKAGE = ROOT/'software/energy-ml-stage105.tar.gz'
RESULT = ROOT/'ntuples/energy_ml_stage105/result.tar.gz'
FILES = ['ml/stage105_point_feasibility.py',
         'workbook/stage105_energy_ml/protocol.json',
         'workbook/stage105_energy_ml/identities.json']


def package():
    assert not (OUT/'complete.json').exists(), 'Do not overwrite an executed protocol'
    ast.parse((ROOT/FILES[0]).read_text())
    with tarfile.open(PACKAGE, 'w:gz', compresslevel=1) as tar:
        for name in FILES:
            tar.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'AnalysisZipFramework/submission/run_ml_stage105.sh', SPOOL/'worker.sh')
    RESULT.parent.mkdir(exist_ok=True)
    print(json.dumps(dict(files=len(FILES), bytes=PACKAGE.stat().st_size, spool=str(SPOOL))))


def collect(archive):
    with tarfile.open(archive or RESULT) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            path = Path(member.name)
            assert not path.is_absolute() and '..' not in path.parts
            assert path.parts[:2] == ('workbook', 'stage105_energy_ml')
            dest = ROOT/path
            content = tar.extractfile(member).read()
            if dest.exists():
                assert dest.read_bytes() == content, dest
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
    with tarfile.open(PACKAGE) as tar:
        for name in FILES:
            assert tar.extractfile(name).read() == (ROOT/name).read_bytes(), name
    (OUT/'packaging_validation.json').write_text(json.dumps(dict(
        passed=True, byte_identical_files=FILES, local_event_calculations=False), indent=2)+'\n')
    normalize_outputs()
    print('collected; worker, frozen protocol and original identities byte-identical')


def normalize_outputs():
    """Render missing TSV cells explicitly; strip SVG trailing spaces, no numbers changed."""
    for path in OUT.glob('*.tsv'):
        rows = list(csv.reader(path.open(), delimiter='\t'))
        with path.open('w') as stream:
            writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
            writer.writerows([[cell if cell else 'NA' for cell in row] for row in rows])
    svg = OUT/'graph_cost.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['package', 'collect'])
    parser.add_argument('--archive')
    args = parser.parse_args()
    package() if args.action == 'package' else collect(args.archive)
