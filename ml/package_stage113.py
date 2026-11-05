"""Standard-library transport, not local event computation."""
import argparse
import ast
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage113_energy_ml'
SPOOL = Path.home()/'condor/nu_muAnalysis/stage113'
PACKAGE = ROOT/'software/energy-ml-stage113.tar.gz'
RESULT = ROOT/'ntuples/energy_ml_stage113/result.tar.gz'
FILES = ['ml/stage113_measure.py', 'ml/stage113_supervise.py',
         'ml/stage112_audit.py', 'ml/stage112_selection.py', 'ml/stage112_statistics.py',
         'ml/audited_features.py', 'ml/configs/audited_features.json', 'build/analysis',
         'AnalysisZipFramework/config/definitions.yaml', 'AnalysisZipFramework/config/ml_definitions.yaml',
         'AnalysisZipFramework/config/ml_low_energy_cuts.yaml', 'AnalysisZipFramework/config/grl_config.yaml',
         'AnalysisZipFramework/include/RDFDefines.h', 'ntuples/energy_ml_stage87/split.npz',
         'workbook/stage111_energy_ml/source_manifest.json',
         'workbook/stage111_energy_ml/experiment_contract.json',
         'workbook/stage112_energy_ml/QA.json', 'workbook/stage112_energy_ml/qa_manifest.json',
         'workbook/stage112_energy_ml/next_execution_contract.json',
         'workbook/stage113_energy_ml/protocol.json']


def package():
    assert not (OUT/'complete.json').exists()
    for name in FILES:
        if name.endswith('.py'):
            ast.parse((ROOT/name).read_text())
    with tarfile.open(PACKAGE, 'w:gz', compresslevel=1) as t:
        for name in FILES:
            t.add(ROOT/name, arcname=name)
    SPOOL.mkdir(parents=True, exist_ok=True)
    (SPOOL/'logs').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'AnalysisZipFramework/submission/run_ml_stage113.sh', SPOOL/'worker.sh')
    RESULT.parent.mkdir(exist_ok=True)
    (OUT/'package.json').write_text(json.dumps(dict(files=FILES, files_count=len(FILES), archive_bytes=PACKAGE.stat().st_size,
                                                   local_event_or_numerical_work=False, spool=str(SPOOL)), indent=2)+'\n')
    print('Packaged', len(FILES), 'files;', PACKAGE.stat().st_size, 'bytes')


def collect():
    with tarfile.open(RESULT) as t:
        for m in t.getmembers():
            if not m.isfile():
                continue
            path = Path(m.name)
            assert path.parts[:2] == ('workbook', 'stage113_energy_ml')
            assert not path.is_absolute() and '..' not in path.parts
            dest = ROOT/path
            content = t.extractfile(m).read()
            if dest.exists():
                assert dest.read_bytes() == content, dest
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
    with tarfile.open(PACKAGE) as t:
        for name in FILES:
            assert t.extractfile(name).read() == (ROOT/name).read_bytes(), name
    (OUT/'transport_validation.json').write_text(json.dumps(dict(passed=True, byte_exact_input_files=len(FILES),
        result_bytes=RESULT.stat().st_size, local_numerical_execution=False), indent=2)+'\n')
    print('Collected; all', len(FILES), 'input files byte-identical')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['package', 'collect'])
    a = p.parse_args()
    package() if a.action == 'package' else collect()
