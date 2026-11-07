"""Test sparse EVNT reading on the already fully linked 91-parent source."""
import json
import gzip
import runpy
import sys
from pathlib import Path

root = Path.cwd()
source = json.loads((root / 'workbook/stage130_energy_ml/source_protocol.json').read_text())['sources'][508]
request = root / 'ntuples/energy_ml_stage130/parentmap_pilot_request.json'
request.write_text(json.dumps(dict(source=source)))
sys.argv = ['stage130_parentmap.py', str(request),
            str(root / 'ntuples/energy_ml_stage130/support_508/selected.npz'),
            str(root / 'workbook/stage130_energy_ml/parentmap_pilot.json')]
runpy.run_path(str(root / 'ml/stage130_parentmap.py'), run_name='__main__')
output = root / 'workbook/stage130_energy_ml/parentmap_pilot.json'
payload = output.read_bytes()
with gzip.open(root / 'ntuples/energy_ml_stage130/parentmap_pilot.json.gz', 'wb') as stream:
    stream.write(payload)
summary = json.loads(payload)
records = summary.pop('records')
summary['maximum_abs_neutrino_energy_difference_GeV'] = max(r['abs_energy_difference_GeV'] for r in records)
summary['complete_identity_records'] = 'ignored ntuples/energy_ml_stage130/parentmap_pilot.json.gz'
output.write_text(json.dumps(summary, indent=2)+'\n')
