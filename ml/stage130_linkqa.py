"""Record-space check of selected event identifiers against complete EVNT entries."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage130'


def main():
    indices = json.loads((OUT / 'support_pilot_contract.json').read_text())['indices']
    rows = []
    for index in indices:
        records = json.loads((CACHE / f'parentlink_{index}.json').read_text())
        lookup = {r['entry']: r for r in records}
        with np.load(CACHE / f'support_{index}/selected.npz') as z:
            matched = 0
            differences = []
            for event, incoming, energy in zip(z['eventID'], z['incoming'], z['truth_E_GeV']):
                record = lookup.get(int(event))
                if record is None:
                    continue
                if not np.array_equal(np.asarray(record['incoming'], 'float32'), incoming.astype('float32')):
                    continue
                matched += 1
                neutrino = [p for p in record['particles'] if abs(p['pdg']) == 14 and p['status'] == 4]
                assert len(neutrino) == 1
                differences.append(abs(neutrino[0]['p'][3]/1000 - energy))
            rows.append(dict(index=index, selected_N=len(z['eventID']), eventID_entry_incoming_exact_N=matched,
                maximum_abs_neutrino_energy_difference_GeV=max(differences, default=0.0)))
    result = dict(rows=rows, selected_N=sum(r['selected_N'] for r in rows),
                  matched_N=sum(r['eventID_entry_incoming_exact_N'] for r in rows))
    result['all_exact'] = result['selected_N'] == result['matched_N']
    (OUT / 'parent_event_entry_validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result, flush=True)
    assert result['all_exact'], 'Do not assume eventID is the EVNT entry when actual closure fails'


if __name__ == '__main__':
    main()
