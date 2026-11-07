"""Lossless text compaction after all exact stage jobs are terminal."""
import gzip
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage146_energy_ml'


def main():
    accounting = json.loads((OUT/'scheduler_accounting.json').read_text())
    summary = json.loads((OUT/'summary.json').read_text())
    assert accounting['live_N'] == 0 and accounting['completed_N'] == 3
    assert all(row.get('ExitCode') == 0 for row in accounting['jobs'])
    assert summary['passed']
    paths = [OUT/name for name in ['pilot_roots.json.gz', 'full_roots.json.gz', 'identity_records.json.gz']]
    payload = {}
    for path in paths:
        with gzip.open(path, 'rt') as stream:
            payload[str(path.relative_to(ROOT))] = stream.read()
    merged = ROOT/'ntuples/energy_ml_stage146/event_records.json.gz'
    with gzip.open(merged, 'wt') as stream:
        json.dump(payload, stream, separators=(',', ':'))
    with gzip.open(merged, 'rt') as stream:
        assert json.load(stream) == payload
    capsule = ROOT/'software/stage146/source_snapshots.tar.gz'
    submissions = sorted(OUT.glob('*_submission.json'))
    transports = []
    with tarfile.open(capsule, 'w:gz') as destination:
        for path in submissions:
            record = json.loads(path.read_text())
            package = ROOT/record['package']['path']
            with tarfile.open(package, 'r:gz') as source:
                for member in source:
                    if not member.name.endswith(('.py', '.sh')):
                        continue
                    data = source.extractfile(member).read()
                    target = tarfile.TarInfo(record['phase']+'/'+member.name)
                    target.size = len(data)
                    destination.addfile(target, io.BytesIO(data))
            transports.append(package)
            transports.append(ROOT/f"ntuples/energy_ml_stage146/{record['phase']}_result.tar.gz")
    deleted = []
    for path in paths+transports:
        if path.exists():
            deleted.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size))
            path.unlink()
    for path in transports:
        if path.parent != ROOT/'ntuples/energy_ml_stage146' and not any(path.parent.iterdir()):
            path.parent.rmdir()
    report = dict(all_jobs_terminal=True, all_event_text_exact=True,
                  merged_event_records=dict(path=str(merged.relative_to(ROOT)), bytes=merged.stat().st_size),
                  source_capsule=dict(path=str(capsule.relative_to(ROOT)), bytes=capsule.stat().st_size),
                  deleted=deleted, deleted_bytes=sum(row['bytes'] for row in deleted),
                  scope='Text equality, no scientific array calculation or SHA; no source HITS/PHYS deletion')
    (OUT/'storage_cleanup.json').write_text(json.dumps(report, indent=2)+'\n')
    print(report)


if __name__ == '__main__':
    main()
