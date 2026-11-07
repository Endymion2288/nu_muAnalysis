"""Lossless event-text compaction and transport cleanup after terminal stage jobs."""
import gzip
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage148_energy_ml'
CACHE = ROOT/'ntuples/energy_ml_stage148'


def main():
    accounting = json.loads((OUT/'scheduler_accounting.json').read_text())
    summary = json.loads((OUT/'summary.json').read_text())
    submissions = sorted(OUT.glob('*_submission.json'))
    assert accounting['live_N'] == 0 and accounting['completed_N'] == len(submissions)
    assert all(row.get('ExitCode') == 0 for row in accounting['jobs']) and summary['passed']
    indices = json.loads((OUT/'support.json').read_text())['selected_indices']
    paths = []
    for index in indices:
        paths += [OUT/f'parent_{index}_lineage.json']
        paths += [CACHE/f'parent_{index}_{suffix}' for suffix in ['qa_hits.json.gz', 'control.json.gz', 'ecal_control.json.gz']]
    payload = {}
    for path in paths:
        if path.suffix == '.gz':
            with gzip.open(path, 'rt') as stream:
                payload[str(path.relative_to(ROOT))] = stream.read()
        else:
            payload[str(path.relative_to(ROOT))] = path.read_text()
    merged = CACHE/'event_records.json.gz'
    with gzip.open(merged, 'wt') as stream:
        json.dump(payload, stream, separators=(',', ':'))
    with gzip.open(merged, 'rt') as stream:
        assert json.load(stream) == payload
    capsule = ROOT/'software/stage148/source_snapshots.tar.gz'
    transports = []
    with tarfile.open(capsule, 'w:gz') as destination:
        for path in submissions:
            record = json.loads(path.read_text())
            package = ROOT/record['package']['path']
            with tarfile.open(package, 'r:gz') as source:
                for member in source:
                    if not member.name.endswith(('.py', '.sh', '.hxx')):
                        continue
                    data = source.extractfile(member).read()
                    target = tarfile.TarInfo(record['phase']+'/'+member.name)
                    target.size = len(data)
                    destination.addfile(target, io.BytesIO(data))
            transports += [package, CACHE/f"{record['phase']}_result.tar.gz"]
    deleted = []
    for path in paths+transports:
        if path.exists():
            deleted.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size))
            path.unlink()
    for path in transports:
        if path.parent != CACHE and not any(path.parent.iterdir()):
            path.parent.rmdir()
    result = dict(all_jobs_terminal=True, all_event_text_exact=True,
                  merged_event_records=dict(path=str(merged.relative_to(ROOT)), bytes=merged.stat().st_size),
                  source_capsule=dict(path=str(capsule.relative_to(ROOT)), bytes=capsule.stat().st_size),
                  deleted=deleted, deleted_bytes=sum(row['bytes'] for row in deleted),
                  scope='Text equality only, no scientific array computation/SHA; original EVNT and other stages untouched')
    (OUT/'storage_cleanup.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    main()
