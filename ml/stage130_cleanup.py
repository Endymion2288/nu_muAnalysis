"""Verify merged arrays, compact source evidence, then remove retired duplicates."""
import gzip
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage130'


def main():
    assert (OUT / 'analysis_complete.json').exists()
    assert json.loads((OUT / 'independent_validation.json').read_text())['max_abs_difference'] < 1e-10
    resources = json.loads((OUT / 'resource_summary.json').read_text())
    assert resources['unique_submitted'] == resources['observed'] == resources['terminal'], 'Do not delete live inputs'
    contract = json.loads((OUT / 'production_contract.json').read_text())
    proof = json.loads((OUT / 'compact_verification.json').read_text())
    assert proof['all_retained_arrays_exact'] and proof['sources_N'] == contract['source_N']
    verified = {r['index']: r for r in proof['sources']}
    evidence, retired, parentmaps = [], [], {}
    # Prove every retained merged array against the original selected shard
    # before deleting any shard or archive. Source roles/metadata are retained.
    for index in contract['all_source_indices']:
        phase = 'support' if index in contract['pilot_reused'] else 'production'
        directory = CACHE / f'{phase}_{index}'
        assert (directory / 'selected.npz').stat().st_size == verified[index]['selected_bytes']
        metadata = {p.name: json.loads(p.read_text()) for p in sorted(directory.glob('*.json'))}
        if 'parentmap.json' in metadata:
            parentmaps[str(index)] = metadata['parentmap.json']
            summary = {k: v for k, v in parentmaps[str(index)].items() if k != 'records'}
            summary['maximum_abs_neutrino_energy_difference_GeV'] = max(
                (r['abs_energy_difference_GeV'] for r in parentmaps[str(index)]['records']), default=0.)
            metadata['parentmap.json'] = summary
        record = dict(index=index, phase=phase, metadata=metadata,
            times={p.name: p.read_text() for p in sorted(directory.glob('*_time.txt'))})
        evidence.append(record)
        retired.append(directory)
    encoded = (json.dumps(evidence, separators=(',', ':'))+'\n').encode()
    compact = OUT / 'source_evidence.json.gz'
    with gzip.open(compact, 'wb', compresslevel=9) as stream:
        stream.write(encoded)
    with gzip.open(compact, 'rb') as stream:
        assert stream.read() == encoded
    parent_payload = (json.dumps(parentmaps, separators=(',', ':'))+'\n').encode()
    with gzip.open(CACHE / 'parentmaps.json.gz', 'wb', compresslevel=9) as stream:
        stream.write(parent_payload)
    with gzip.open(CACHE / 'parentmaps.json.gz', 'rb') as stream:
        assert stream.read() == parent_payload
    removed_bytes = 0
    for path in retired:
        removed_bytes += sum(p.stat().st_size for p in path.rglob('*') if p.is_file())
        shutil.rmtree(path)
    # Tar returns repeat the now-verified shard and evidence. All submitted
    # software packages are retired only after the complete scheduler ledger.
    removable = list(CACHE.glob('production_*.tar.gz')) + list(CACHE.glob('support_*.tar.gz'))
    for submission in OUT.glob('*_submission_[0-9]*.json'):
        record = json.loads(submission.read_text())
        removable.append(ROOT / record['package']['path'])
    for path in set(removable):
        if path.exists():
            removed_bytes += path.stat().st_size
            path.unlink()
    # The individual byte-roundtrip audits are losslessly consolidated too.
    audits = {p.name: json.loads(p.read_text()) for p in OUT.glob('production_*_audit.json')}
    payload = (json.dumps(audits, separators=(',', ':'))+'\n').encode()
    with gzip.open(OUT / 'production_transfer_audits.json.gz', 'wb', compresslevel=9) as stream:
        stream.write(payload)
    with gzip.open(OUT / 'production_transfer_audits.json.gz', 'rb') as stream:
        assert stream.read() == payload
    for name in audits:
        removed_bytes += (OUT / name).stat().st_size
        (OUT / name).unlink()
    report = dict(source_shards_verified=len(retired), merged_array_roundtrip_exact=True,
        compact_source_evidence_bytes=compact.stat().st_size,
        removed_duplicate_bytes=removed_bytes, all_submitted_attempts_terminal=True,
        retained='mergednew_input/curve membership/models/predictions;compact all-source identity/cutflow/calibration/timing and transport audits;ignored parentmaps.json.gz and pilot completeEVNT records',
        restore='Per-source selected NPZ can be reconstructed from mergednew_input source masks for retained fields;source_evidence.json.gz retains aggregate QA;ignored parentmaps.json.gz preserves per-entry identity evidence;immutable code/descriptor/source contract regenerate omitted intermediate fields')
    (OUT / 'cleanup.json').write_text(json.dumps(report, indent=2)+'\n')
    print(report, flush=True)


if __name__ == '__main__':
    main()
