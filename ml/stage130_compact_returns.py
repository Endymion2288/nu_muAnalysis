"""Lossless pilot-parent bundle and deletion of verified science returns."""
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage130'


def main():
    resources = json.loads((OUT / 'resource_summary.json').read_text())
    assert resources['terminal'] == resources['unique_submitted']
    assert (OUT / 'cleanup.json').exists()
    indices = json.loads((OUT / 'support_pilot_contract.json').read_text())['indices']
    payloads = {f'parentlink_{i}.json': (CACHE / f'parentlink_{i}.json').read_bytes() for i in indices}
    bundle = CACHE / 'pilot_complete_parents.tar.gz'
    with tarfile.open(bundle, 'w:gz') as archive:
        for name, payload in payloads.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    with tarfile.open(bundle) as archive:
        for name, payload in payloads.items():
            assert archive.extractfile(name).read() == payload
    removed = []
    for name, payload in payloads.items():
        (CACHE / name).unlink()
        removed.append(dict(path=str((CACHE / name).relative_to(ROOT)), bytes=len(payload)))
    for path in sorted(CACHE.glob('*_result.tar.gz')):
        phase = path.name.removesuffix('_result.tar.gz')
        transfer = json.loads((OUT / f'{phase}_transfer.json').read_text())
        assert transfer['byte_roundtrip_verified']
        removed.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size))
        path.unlink()
    result = dict(pilot_parent_files=len(payloads), bundle=str(bundle.relative_to(ROOT)),
        bundle_bytes=bundle.stat().st_size, all_member_bytes_exact=True,
        removed_duplicate_bytes=sum(r['bytes'] for r in removed), removed=removed,
        restore='Python tarfile extracts/reads exact parentlink_<index>.json members from pilot_complete_parents.tar.gz;no newEVNT job needed')
    (OUT / 'return_compaction.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result, flush=True)


if __name__ == '__main__':
    main()
