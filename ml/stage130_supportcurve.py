"""Measured unique-family and effective support, including difficult strata."""
import json

import numpy as np

from stage119_curve_common import masks
from stage130_prepare import CACHE, OUT, load, table


def main():
    datasets = dict(old=load('ntuples/energy_ml_stage119/old_input.npz'),
                    new=load(CACHE / 'new_input.npz'))
    membership = load(CACHE / 'curve_membership.npz')
    rows = []
    for side, data in datasets.items():
        policies = {f'role{role}': data['role'] == role for role in sorted(set(data['role']))}
        for arm in ['N0', 'N2']:
            policies['curve_'+arm] = np.isin(np.arange(len(data['role'])), membership[side+'_'+arm])
        for name, selected in policies.items():
            _, gid, counts = np.unique(data['incoming'][selected].astype('float32'), axis=0,
                                       return_inverse=True, return_counts=True)
            w = 1/counts[gid]
            sd = {k: v[selected] for k, v in data.items() if isinstance(v, np.ndarray) and len(v) == len(selected)}
            for layer, mask in masks(sd).items():
                ww = w[mask]
                rows.append(dict(side=side, selection=name, stratum=layer, records_N=int(mask.sum()),
                    incoming_N=len(np.unique(gid[mask])), family_weight_sum=float(ww.sum()),
                    record_weight_ESS=float(ww.sum()**2/(ww @ ww)) if len(ww) else 0))
    # Combined controlled-curve family counts must match the frozen allocation.
    for arm in ['N0', 'N2']:
        actual = sum(r['incoming_N'] for r in rows if r['selection'] == 'curve_'+arm and r['stratum'] == 'all')
        protocol = json.loads((OUT / 'curve_protocol.json').read_text())
        assert actual == sum(r['curve_'+arm+'_incoming'] for r in protocol['scale_support'])
    table('family_support.tsv', rows)
    print('Measured', len(rows), 'support strata; no fits or forward', flush=True)


if __name__ == '__main__':
    main()
