"""Freeze literal known paths from retained text manifests, without EOS probes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage168_energy_ml'
assert not (OUT / 'inputs.json').exists()
p = json.loads((ROOT / 'workbook/stage130_energy_ml/source_protocol.json').read_text())
sources = {r['index']: r for r in p['sources']}
rows = []
for r in sorted(p['inventory'], key=lambda x: x['run']):
    components = {sources[i]['component'] for i in r['source_indices']}
    assert len(components) == 1 and r['EVNT']
    rows.append(dict(run=r['run'], nominal=r['nominal'], component=next(iter(components)), path=r['EVNT']))
assert [r['run'] for r in rows] == list(range(200080, 200102))
pilots = []
for label, predicate in [
    ('alternative_pi', lambda r: r['component'] == 'pi' and not r['nominal']),
    ('nominal_pi', lambda r: r['component'] == 'pi' and r['nominal']),
    ('k', lambda r: r['component'] == 'k'), ('charm', lambda r: r['component'] == 'charm')]:
    record = next(r for r in rows if predicate(r))
    if record['path'] not in [r['path'] for r in pilots]:
        pilots.append(dict(**record, selection=label))
unique = []
for r in rows:
    if r['path'] not in unique:
        unique.append(r['path'])
result = dict(run_mapping=rows, unique_paths=unique, pilot=pilots,
    duplicate_paths={path: [r['run'] for r in rows if r['path'] == path] for path in unique
                     if sum(r['path'] == path for r in rows) > 1},
    source='workbook/stage130_energy_ml/source_protocol.json', event_data_opened=False,
    directory_or_file_probes=False)
(OUT / 'inputs.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
