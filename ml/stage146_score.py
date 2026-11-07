"""Apply immutable Stage145 scores and match retained generator roots by identity."""
import csv
import gzip
import json
import resource
import time
from collections import Counter
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

from stage145_mu_joint import extract, wilson

OUT = Path('workbook/stage146_energy_ml')


def same_float32(left, right):
    return np.array_equal(np.asarray(left, dtype=np.float32), np.asarray(right, dtype=np.float32))


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    plan = json.loads((OUT/'protocol.json').read_text())
    old_plan = json.loads(Path('workbook/stage145_energy_ml/protocol.json').read_text())
    models = json.loads(Path(plan['score_models']).read_text())['1']
    data, extraction = extract(old_plan['sources'][1], old_plan['entry_stop'])
    with gzip.open(OUT/'full_roots.json.gz', 'rt') as stream:
        native = json.load(stream)
    by_key = {}
    for row in native:
        by_key.setdefault((row['run'], row['event']), []).append(row)
    branches = ['run', 'eventID', 'truth_pdg', 'truth_barcode', 'truth_px', 'truth_py', 'truth_pz',
                'truth_prod_x', 'truth_prod_y', 'truth_prod_z']
    with uproot.open(plan['PHYS'], array_cache=None) as root:
        tree = root['nt']
        missing = sorted(set(branches)-set(tree.keys()))
        assert not missing, missing
        arrays = tree.arrays(branches, entry_stop=old_plan['entry_stop'])
        identity_bytes = int(root.file.source.num_requested_bytes)
    native_keys = set(by_key)
    phys_keys = [(int(run), int(event)) for run, event in zip(arrays.run, arrays.eventID)]
    phys_counts = Counter(phys_keys)
    identity_reasons = Counter()
    all_identity = []
    for entry in range(len(arrays)):
        value = arrays[entry]
        key = (int(value.run), int(value.eventID))
        candidates = by_key.get(key, [])
        reason, root_barcodes = 'no_native_run_event', []
        retained_mu = False
        if phys_counts[key] > 1:
            reason = 'duplicate_PHYS_identity'
        elif len(candidates) > 1:
            reason = 'duplicate_native_identity'
        elif candidates:
            graphs = candidates[0]['graphs']
            roots = [p for graph in graphs for p in graph['roots']]
            graph_ok = bool(graphs) and all(graph['duplicate_id_N'] == 0 and graph['missing_parent_edges'] == 0
                                           and graph['cycle_or_blocked_N'] == 0 and graph['root_N'] > 0 for graph in graphs)
            retained_mu = graph_ok and all(abs(p['pdg']) == 13 for p in roots)
            reason = 'graph_incomplete' if not graph_ok else 'non_mu_root'
            if retained_mu:
                reason = 'root_identity_mismatch'
                p3 = np.column_stack([ak.to_numpy(value['truth_'+axis]) for axis in ['px', 'py', 'pz']])
                vertex = np.column_stack([ak.to_numpy(value['truth_prod_'+axis]) for axis in ['x', 'y', 'z']])
                pdg = ak.to_numpy(value.truth_pdg)
                barcodes = ak.to_numpy(value.truth_barcode)
                for particle in roots:
                    found = [index for index in range(len(pdg))
                             if int(pdg[index]) == particle['pdg'] and particle['vertex'] is not None
                             and same_float32(p3[index], particle['p4'][:3])
                             and same_float32(vertex[index], particle['vertex'][:3])]
                    if len(found) != 1:
                        break
                    root_barcodes.append(int(barcodes[found[0]]))
                else:
                    if len(set(root_barcodes)) == len(roots):
                        reason = 'matched_retained_mu_root'
        identity_reasons[reason] += 1
        all_identity.append(dict(entry=entry, run=key[0], event=key[1], reason=reason,
                                 matched_root_barcodes=root_barcodes, retained_mu_graph=retained_mu,
                                 recorded_nonmu_truth=bool(ak.any(abs(value.truth_pdg) != 13))))
    selected = [all_identity[int(entry)] for entry in data['entry']]
    label = np.asarray([row['reason'] for row in selected])
    known = label == 'matched_retained_mu_root'
    # Preserve original denominator and reproduce all fixed scores before subgroups.
    old_rows = list(csv.DictReader(Path('workbook/stage145_energy_ml/heldout.tsv').open(), delimiter='\t'))
    rows, reproduction = [], []
    entry, point = data['entry'], data['point']
    heldout = entry % 4 == 3
    scores = {}
    for policy, model in models.items():
        y = np.arcsinh(data['charge'])
        if policy == 'Qshape30':
            y = np.column_stack([y, np.arcsinh(data['shape']/10)])
        available = np.all(np.isfinite(point), axis=1) & np.all(np.isfinite(y), axis=1)
        in_range = np.all((point >= model['state_lo']) & (point <= model['state_hi']), axis=1)
        design = np.column_stack([np.ones(len(point)), (point-model['state_mean'])/model['state_scale']])
        residual = y-design@np.asarray(model['beta'])
        score = np.einsum('ni,ij,nj->n', residual, np.linalg.inv(np.asarray(model['covariance'])), residual)
        alarm = score > model['threshold']
        scores[policy] = dict(score=score, alarm=alarm, scored=available & in_range)
        groups = dict(all=np.ones(len(entry), bool), overflow=np.any((data['status'] & 4) != 0, axis=1),
                      high_activity=data['charge'].sum(axis=1) > model['high_activity_train_sum_raw_charge99_pC'],
                      pz50_100=data['pz'] < 100)
        for group, mask in groups.items():
            for category, category_mask in [('all', np.ones(len(entry), bool)), ('matched_mu_root', known), ('unknown', ~known)]:
                denominator = heldout & mask & category_mask
                use = denominator & available & in_range
                n, k = int(use.sum()), int((use & alarm).sum())
                low, high = wilson(k, n)
                row = dict(policy=policy, group=group, ancestry=category, original_heldout_N=int(denominator.sum()),
                           scored_N=n, alerts=k, fraction=k/n if n else None, Wilson95_low=low, Wilson95_high=high,
                           missing_N=int((denominator & ~available).sum()), outside_range_N=int((denominator & available & ~in_range).sum()))
                rows.append(row)
                if category == 'all':
                    old = next(r for r in old_rows if r['source_index'] == '1' and r['policy'] == policy and r['group'] == group)
                    checks = {field: int(old[field]) == row[field] for field in ['original_heldout_N', 'scored_N', 'alerts', 'missing_N']}
                    checks['outside_range_N'] = int(old['outside_fit_state_range_N']) == row['outside_range_N']
                    reproduction.append(dict(policy=policy, group=group, checks=checks))
    assert all(all(r['checks'].values()) for r in reproduction), reproduction
    with (OUT/'heldout_by_root.tsv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    # Compact audit keeps every input identity and selected score without full readout arrays.
    for index, row in enumerate(selected):
        row['heldout'] = bool(heldout[index])
        row['groups'] = {group: bool(mask[index]) for group, mask in groups.items()}
        row['scores'] = {policy: dict(value=float(values['score'][index]) if np.isfinite(values['score'][index]) else None,
                                     alert=bool(values['alarm'][index]), scored=bool(values['scored'][index]))
                         for policy, values in scores.items()}
    with gzip.open(OUT/'identity_records.json.gz', 'wt') as stream:
        json.dump(all_identity, stream, separators=(',', ':'), allow_nan=False)
    report = dict(passed=True, input_N=len(arrays), selected_N=len(entry), native_N=len(native),
                  native_root_PDG_counts=dict(Counter(str(p['pdg']) for row in native for graph in row['graphs'] for p in graph['roots'])),
                  native_particle_N=sum(graph['particle_N'] for row in native for graph in row['graphs']),
                  native_missing_parent_edges=sum(graph['missing_parent_edges'] for row in native for graph in row['graphs']),
                  native_duplicate_particle_ids=sum(graph['duplicate_id_N'] for row in native for graph in row['graphs']),
                  native_cycle_or_blocked_N=sum(graph['cycle_or_blocked_N'] for row in native for graph in row['graphs']),
                  native_unit_values=sorted(set((graph['momentum_unit'], graph['length_unit']) for row in native for graph in row['graphs'])),
                  native_unique_run_event_N=len(native_keys), PHYS_run_values=sorted(set(int(x) for x in arrays.run)),
                  PHYS_duplicate_run_event_entries=sum(count for count in phys_counts.values() if count > 1),
                  native_run_values=sorted(set(row['run'] for row in native)), identity_reasons=dict(identity_reasons),
                  selected_identity_reasons=dict(Counter(label)),
                  matched_selected_with_nonmu_truth_N=sum(row['recorded_nonmu_truth'] and row['reason'] == 'matched_retained_mu_root' for row in selected),
                  fixed_score_reproduction=reproduction, extraction=extraction, identity_read_bytes=identity_bytes,
                  CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
                  RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  fits=0, new_G4=0, reserved_forward=0, radiation_process_certified=False,
                  scope='Observed PG retained mu-root control, not independently confirmed population FPR, G4 process classification or current nu/data transfer')
    (OUT/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    print(report, flush=True)


if __name__ == '__main__':
    main()
