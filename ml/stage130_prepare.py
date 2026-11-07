"""Freeze full-depth incoming-family roles and original-scale nested memberships."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from latent_transfer_diagnostics import check_x

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage130'


def load(path):
    with np.load(ROOT / path) as z:
        return {k: z[k] for k in z.files if k != 'metadata_json'}


def table(name, rows):
    with (OUT / name).open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(k for r in rows for k in r)),
                                delimiter='\t', lineterminator='\n', quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader()
        writer.writerows(rows)


def main():
    plan = json.loads((OUT / 'source_protocol.json').read_text())
    contract = json.loads((OUT / 'production_contract.json').read_text())
    old = load('ntuples/energy_ml_stage119/old_input.npz')
    assert len(old['role']) == 89033 and int((old['role'] == 0).sum()) == 17657
    check_x(old['x'])
    known = set()
    paths = json.loads((ROOT / 'workbook/stage119_energy_ml/exposure_inputs.json').read_text())
    for path in paths + ['ntuples/energy_ml_stage119/curve_input.npz']:
        with np.load(ROOT / path) as z:
            known.update(map(tuple, z['incoming'].astype('float32')))
    parts, audits = [], []
    pilot_identity = {row['index']: row for row in
        json.loads((OUT / 'parent_event_entry_validation.json').read_text())['rows']}
    fields = ['x', 'incoming', 'run', 'eventID', 'input_entry', 'truth_E_GeV', 'y_lepton',
              'primary_p_GeV', 'primary_valid', 'confirmed', 'vertex_z_mm',
              'raw_charge', 'status', 'calo_status']
    for index in contract['all_source_indices']:
        phase = 'support' if index in contract['pilot_reused'] else 'production'
        directory = CACHE / f'{phase}_{index}'
        assert int((directory / 'exitcode.txt').read_text()) == 0, index
        source = plan['sources'][index]
        assert source['eligible'] and not source['old_locked'] and not source['nominal']
        with np.load(directory / 'selected.npz') as z:
            part = {k: z[k] for k in fields}
            n = len(z['x'])
            part['pz'] = z['reco_pz_GeV']
            check_x(part['x'])
        identity = pilot_identity[index] if phase == 'support' else json.loads((directory / 'parentmap.json').read_text())
        assert identity['selected_N'] == identity['eventID_entry_incoming_exact_N'] == n, index
        part.update(source=np.full(n, index), component=np.full(n, source['component']),
                    group=np.full(n, source['group']),
                    initial_role=np.full(n, dict(train=1, cal=2, test=3)[source['inherited_role']], 'int8'))
        parts.append(part)
        audits.append(dict(index=index, phase=phase, run=source['run'], selected_N=n,
                           inherited_role=source['inherited_role'], actual_EVNT_entry_matches=n))
    new = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    keys, first, gid = np.unique(new['incoming'].astype('float32'), axis=0,
                                 return_index=True, return_inverse=True)
    is_known = np.array([tuple(k) in known for k in keys])
    priority = np.zeros(len(keys), 'int8')
    np.maximum.at(priority, gid, new['initial_role'])
    family_role = priority.copy()
    for j, key in enumerate(keys):
        if is_known[j]:
            family_role[j] = 0
        elif family_role[j] == 1:
            digest = hashlib.blake2b(np.asarray(key, dtype='<f4').tobytes(), digest_size=8,
                                    person=b'nuMu130').digest()
            if int.from_bytes(digest, 'little') % 100 < 15:
                family_role[j] = 4
    new['role'] = np.where((new['initial_role'] == priority[gid]) | (family_role[gid] == 4),
                           family_role[gid], 0).astype('int8')
    new['key_id'] = gid
    # No new training key may overlap any original role, including quarantine.
    assert not set(map(tuple, new['incoming'][new['role'] == 1].astype('float32'))) & known
    for a, b in [(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)]:
        assert not set(gid[new['role'] == a]) & set(gid[new['role'] == b])
    np.savez_compressed(CACHE / 'new_input.npz', **new)
    table('production_sources.tsv', audits)
    counts = []
    for role in range(5):
        for lo, hi in [(50, 100), (100, 200), (200, np.inf)]:
            use = (new['role'] == role) & (new['truth_E_GeV'] >= lo) & (new['truth_E_GeV'] < hi)
            counts.append(dict(role=role, E_low_GeV=lo, E_high_GeV=hi, records_N=int(use.sum()),
                               incoming_N=len(np.unique(gid[use]))))
    table('new_role_support.tsv', counts)

    # All views of an incoming family enter together. Coarse cell labels are
    # assigned from its canonical first view, as in Stage119, before any fit.
    inventory = {r['run']: r['EVNT'] for r in plan['inventory']}
    combined = {k: np.concatenate([old[k], new[k]]) for k in
                ['incoming', 'truth_E_GeV', 'y_lepton', 'vertex_z_mm', 'component', 'run', 'role']}
    training = np.flatnonzero(combined['role'] == 1)
    unique, canonical, inv = np.unique(combined['incoming'][training].astype('float32'),
                                       axis=0, return_index=True, return_inverse=True)
    canonical = training[canonical]
    cells, by_cell = [], {}
    for family, row in enumerate(canonical):
        energy, y, z = (combined[k][row] for k in ['truth_E_GeV', 'y_lepton', 'vertex_z_mm'])
        path = inventory[int(combined['run'][row])]
        flux = Path(path).name.split('.EVNT')[0].replace('_', '-')
        year = '22' if '22_23_crossing' in path else '24'
        band = int(np.searchsorted([100, 200], energy, side='right'))
        cell = f'{band}:{year}:{flux}:{combined["component"][row]}:y{int(y >= .8) if np.isfinite(y) and 0 <= y < 1 else 2}:z{int(z >= -1950)}'
        cells.append(cell)
        by_cell.setdefault(cell, []).append(family)
    old_train = old['role'] == 1
    old_counts = [len(np.unique(old['incoming'][old_train & (old['truth_E_GeV'] >= lo) &
                      (old['truth_E_GeV'] < hi)].astype('float32'), axis=0))
                  for lo, hi in [(50, 100), (100, 200), (200, np.inf)]]
    rng = np.random.default_rng(20261107301)
    chosen = [[], []]
    composition, scale_support = [], []
    for band, target in enumerate(old_counts):
        eligible = sorted(c for c in by_cell if c.startswith(str(band) + ':'))
        cap = np.array([len(by_cell[c]) // 2 for c in eligible])
        n0 = min(target, int(cap.sum()))
        expected = cap * (n0 / cap.sum()) if cap.sum() else cap.astype(float)
        allocation = np.floor(expected).astype(int)
        order = np.argsort(-(expected - allocation), kind='stable')
        for j in order[:n0-int(allocation.sum())]:
            allocation[j] += 1
        assert int(allocation.sum()) == n0 and np.all(allocation <= cap)
        for cell, n in zip(eligible, allocation):
            order = rng.permutation(by_cell[cell])
            for k in range(2):
                chosen[k].extend(order[:int(n)*2**k])
            composition.append(dict(cell=cell, available_families=len(order), N0=int(n), N2=int(n)*2))
        scale_support.append(dict(energy_band=band, old_N0_incoming=target,
                                  curve_N0_incoming=n0, curve_N2_incoming=2*n0,
                                  original_scale_reached=n0 == target))
    membership = {}
    for k, name in enumerate(['N0', 'N2']):
        use = training[np.isin(inv, chosen[k])]
        membership['old_' + name] = use[use < len(old['role'])]
        membership['new_' + name] = use[use >= len(old['role'])] - len(old['role'])
        assert len(np.unique(combined['incoming'][use].astype('float32'), axis=0)) == len(chosen[k])
    np.savez_compressed(CACHE / 'curve_membership.npz', **membership)
    table('curve_composition.tsv', composition)
    protocol = dict(stage=130, scale_support=scale_support, role_counts=counts,
        seed=20261107301, no_model_outcomes_before_freeze=True,
        original_scale_reached=all(r['original_scale_reached'] for r in scale_support),
        quantity_effect='N0/N2 within one fixed full-depth pooled flux/composition; not a pure old nominal flux extension',
        augmented_effect='old-full train plus all new train; quantity and flux/mixture both change',
        canonical_family='conservative float32 native incoming; first-view cell, all views retained together',
        rare_cells='less than2 families excluded only from controlled curve; kept in augmented and evaluation pools',
        reserve_role=4, reserve_predictions=0, old_quarantine_predictions=0,
        independence='full original GENIE seed/history not certified; unobserved historical exposure remains a limitation',
        baseline=json.loads((ROOT / 'workbook/stage87_energy_ml/protocol.json').read_text())['baseline'])
    (OUT / 'curve_protocol.json').write_text(json.dumps(protocol, indent=2)+'\n')
    print('Frozen original-scale support', scale_support, flush=True)


if __name__ == '__main__':
    main()
