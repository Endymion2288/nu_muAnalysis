"""Freeze source lists and literal retained metadata paths, without data probes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage169_energy_ml'
assert not (OUT/'inputs.json').exists()
p = json.loads((OUT/'protocol.json').read_text())
contract = json.loads((ROOT/p['inputs']['completed_sources']).read_text())
proof = json.loads((ROOT/p['inputs']['actual_log_bounds']).read_text())
completed = contract['all_source_indices']; pilot = [r['index'] for r in proof['sources']]
assert len(completed)==len(set(completed))==666 and len(pilot)==len(set(pilot))==16
assert set(pilot)<=set(completed) and 508 in pilot
files = [value for key,value in p['inputs'].items() if key != 'native_scan_summaries']
native = {str(i):f'workbook/stage130_energy_ml/parentlink_{i}.json' for i in pilot}
files += list(native.values())
result = dict(completed_sources=completed,pilot_sources=pilot,native_summaries=native,files=files,
              source_manifest_N_expected=1134,directory_or_data_probes=False,event_arrays_opened=False)
(OUT/'inputs.json').write_text(json.dumps(result,indent=2)+'\n')
print('Frozen666 completed sources,16 originalpilot/native summaries; no data probes')
