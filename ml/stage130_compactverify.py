"""Condor array-by-array proof before local stdlib duplicate cleanup."""
import json

import numpy as np

from stage130_prepare import CACHE, OUT, load


def main():
    contract = json.loads((OUT / 'production_contract.json').read_text())
    data = load(CACHE / 'new_input.npz')
    rows, schemas = [], []
    for index in contract['all_source_indices']:
        phase = 'support' if index in contract['pilot_reused'] else 'production'
        directory = CACHE / f'{phase}_{index}'
        part = load(directory / 'selected.npz')
        use = np.flatnonzero(data['source'] == index)
        assert len(use) == len(part['x'])
        compared = sorted(part.keys() & data.keys())
        for key in compared:
            np.testing.assert_array_equal(part[key], data[key][use])
        np.testing.assert_array_equal(part['reco_pz_GeV'], data['pz'][use])
        schema = compared+['reco_pz_GeV→pz']
        if schema not in schemas:
            schemas.append(schema)
        rows.append(dict(index=index, phase=phase, records_N=len(use),
                         selected_bytes=(directory / 'selected.npz').stat().st_size,
                         schema_index=schemas.index(schema)))
    proof = dict(sources_N=len(rows), records_N=len(data['x']),
                 all_retained_arrays_exact=True, sources=rows, array_schemas=schemas,
                 scope='immutable copied shards vs newly merged input; no event quality deletion')
    (OUT / 'compact_verification.json').write_text(json.dumps(proof, indent=2)+'\n')
    print('Verified merged arrays for', len(rows), 'sources', flush=True)


if __name__ == '__main__':
    main()
