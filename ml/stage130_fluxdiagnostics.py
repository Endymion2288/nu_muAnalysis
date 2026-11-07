"""Fixed per-flux/crossing diagnostics; no extra fits or independent-run claim."""
import json

import numpy as np

from stage119_curve_common import masks
from stage119_reportcurve import metrics
from stage130_prepare import ROOT, OUT, CACHE, load, table


def main():
    inventory = {r['run']: r for r in json.loads((OUT / 'source_protocol.json').read_text())['inventory']}
    rows = []
    for side, data in [('old', load('ntuples/energy_ml_stage119/old_input.npz')),
                       ('new', load(CACHE / 'new_input.npz'))]:
        predictions = load(ROOT / f'ml/artifacts/stage130/{side}_evaluation_predictions.npz')
        for role in [2, 3]:
            for run in sorted(set(data['run'][data['role'] == role])):
                selected = (data['role'] == role) & (data['run'] == run)
                ix = np.flatnonzero(selected)
                sd = {k: v[ix] for k, v in data.items() if isinstance(v, np.ndarray) and len(v) == len(selected)}
                _, gid, counts = np.unique(sd['incoming'].astype('float32'), axis=0,
                                           return_inverse=True, return_counts=True)
                w = 1/counts[gid]
                for layer, mask in masks(sd).items():
                    if not mask.any():
                        continue
                    for name, prediction in predictions.items():
                        error = prediction[ix[mask]] - np.log(sd['truth_E_GeV'][mask])
                        rows.append(dict(side=side, role=role, run=int(run), EVNT=inventory[int(run)]['EVNT'],
                            stratum=layer, model=name, records_N=int(mask.sum()),
                            incoming_N=len(np.unique(gid[mask])),
                            **metrics(error, w[mask])))
    table('flux_diagnostics.tsv', rows)
    (OUT / 'flux_diagnostics_scope.json').write_text(json.dumps(dict(
        fits=0, reserve_forward=0, metrics='descriptive per-run family-weighted risks, same frozen predictions',
        uncertainty='no run-level independence or source confidence intervals inferred; common incoming can span runs',
        purpose='separate pooled quantity/mixture results from per-flux and crossing-angle response shifts; no winner selection'), indent=2)+'\n')
    print('Per-flux descriptive risk rows', len(rows), flush=True)


if __name__ == '__main__':
    main()
