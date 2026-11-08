"""Deduplicate source bytes while preserving every executed phase/path revision."""
import json
import tarfile
from pathlib import Path

from stage158_finalize import archive_exact

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage166_energy_ml'
target = ROOT / 'software/stage166/source_snapshots.tar.gz'
assert not (OUT / 'source_compaction.json').exists()
assert json.loads((OUT / 'storage_cleanup.json').read_text())['all_jobs_terminal']
with tarfile.open(target) as archive:
    original = {r.name: archive.extractfile(r).read() for r in archive if r.isfile()}
assert 'source_versions.json' not in original
old_bytes = target.stat().st_size
unique, seen, index = {}, {}, {}
for name, data in original.items():
    if data not in seen:
        seen[data] = name
        unique[name] = data
    index[name] = seen[data]
unique['source_versions.json'] = (json.dumps(index, indent=2) + '\n').encode()
temporary = target.with_name('source_snapshots_compact.tar.gz')
archive_exact(temporary, unique)
with tarfile.open(temporary) as archive:
    restored = {r.name: archive.extractfile(r).read() for r in archive if r.isfile()}
    actual = json.loads(restored['source_versions.json'])
    assert actual == index
    assert all(restored[actual[name]] == data for name, data in original.items())
temporary.replace(target)
record = dict(passed=True, original_logical_members=len(original), unique_content_members=len(unique) - 1,
    all_original_phase_paths_reconstructed_exact=True, original_archive_bytes=old_bytes,
    final_archive_bytes=target.stat().st_size, reduced_archive_bytes=old_bytes - target.stat().st_size,
    archive=str(target.relative_to(ROOT)), index_member='source_versions.json', SHA_used=False,
    event_inputs_opened=False)
(OUT / 'source_compaction.json').write_text(json.dumps(record, indent=2) + '\n')
p = OUT / 'storage_cleanup.json'; storage = json.loads(p.read_text())
for r in storage['archives']:
    if r['path'] == str(target.relative_to(ROOT)): r['bytes'] = target.stat().st_size
storage['source_version_index'] = 'source_compaction.json'
p.write_text(json.dumps(storage, indent=2) + '\n')
print(record)
