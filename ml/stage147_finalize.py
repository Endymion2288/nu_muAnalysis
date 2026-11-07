"""Compact tail witnesses and submitted sources, preserving exact text."""
import gzip
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage147_energy_ml'


def main():
    accounting = json.loads((OUT/'scheduler_accounting.json').read_text())
    assert accounting['live_N'] == 0 and accounting['completed_N'] == 1
    assert all(row.get('ExitCode') == 0 for row in accounting['jobs'])
    assert json.loads((OUT/'summary.json').read_text())['passed']
    original = OUT/'tail_witnesses.json'
    text = original.read_text()
    witness = ROOT/'ntuples/energy_ml_stage147/tail_witnesses.json.gz'
    with gzip.open(witness, 'wt') as stream:
        stream.write(text)
    with gzip.open(witness, 'rt') as stream:
        assert stream.read() == text
    record = json.loads((OUT/'control_submission.json').read_text())
    package = ROOT/record['package']['path']
    capsule = ROOT/'software/stage147/source_snapshots.tar.gz'
    with tarfile.open(package, 'r:gz') as source, tarfile.open(capsule, 'w:gz') as destination:
        for member in source:
            if not member.name.endswith('.py'):
                continue
            data = source.extractfile(member).read()
            target = tarfile.TarInfo(member.name)
            target.size = len(data)
            destination.addfile(target, io.BytesIO(data))
    deleted = []
    for path in [original, package, ROOT/'ntuples/energy_ml_stage147/control_result.tar.gz']:
        deleted.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size))
        path.unlink()
    if not any(package.parent.iterdir()):
        package.parent.rmdir()
    result = dict(all_jobs_terminal=True, witness_text_exact=True,
                  witness=dict(path=str(witness.relative_to(ROOT)), bytes=witness.stat().st_size),
                  source_capsule=dict(path=str(capsule.relative_to(ROOT)), bytes=capsule.stat().st_size),
                  deleted=deleted, deleted_bytes=sum(row['bytes'] for row in deleted),
                  scope='Text compaction only; original HITS/PHYS and Stage146 event records untouched')
    (OUT/'storage_cleanup.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
