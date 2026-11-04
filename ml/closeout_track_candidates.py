"""Stage95 saved-table audit and original Stage94 X groups; no new event reads."""
import argparse
import csv
import json
import math
import time
from collections import Counter

import numpy as np

from track_candidate_information import CACHE, OUT, REPO, SEED, cost, save, table


def read(path):
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def prepare_groups():
    plan = json.loads((CACHE / 'cohort.json').read_text())
    with np.load(REPO / 'ntuples/energy_ml_stage94/evaluation_input.npz') as data:
        rows = np.array([r['row'] for r in plan['records']])
        idx = np.searchsorted(data['row'], rows)
        np.testing.assert_array_equal(data['row'][idx], rows)
        table('X_groups.tsv', [dict(row=int(row), X_calo=int(calo), X_activity=int(activity))
                              for row, calo, activity in zip(rows, data['X_calo'][idx], data['X_activity'][idx])])


def main():
    start = time.perf_counter(), time.process_time()
    plan = json.loads((CACHE / 'cohort.json').read_text())
    metadata = {r['row']: r for r in plan['records']}
    events = read(CACHE / 'events.tsv')
    nodes = read(CACHE / 'candidates.tsv')
    pairs = read(CACHE / 'relations.tsv')
    groups = {int(r['row']): r for r in read(OUT / 'X_groups.tsv')}
    assert len(events) == len(metadata) == len(groups) == plan['N']
    ids = np.array([int(r['row']) for r in events])
    available = np.array([r['available'] == 'True' for r in events])
    ntracks = np.array([float(r['n_tracks']) for r in events])
    pz = np.array([metadata[int(i)]['pz_GeV'] for i in ids])
    role = np.array([metadata[int(i)]['role'] for i in ids])
    status = np.array([metadata[int(i)]['status_other'] for i in ids])
    masks = dict(X_pz50_100=pz < 100, X_pz100_200=(pz >= 100) & (pz < 200),
                 X_pz200_plus=pz >= 200, X_status_valid=~status, X_status_other=status)
    for name in ['calo', 'activity']:
        values = np.array([int(groups[int(i)]['X_' + name]) for i in ids])
        for j in [-1, 0, 1, 2]:
            masks[f'X_{name}_{j}'] = values == j
    masks.update({'cal_' + name: value & (role == 2) for name, value in list(masks.items())})
    rng = np.random.default_rng(SEED)
    draw = np.zeros((500, len(events)), dtype=np.int16)
    buckets = {}
    for j, row in enumerate(ids):
        r = metadata[int(row)]
        buckets.setdefault((r['source'], r['pz_GeV'] < 100, r['status_other']), []).append(j)
    for values in buckets.values():
        draw[:, values] = rng.multinomial(len(values), np.full(len(values), 1 / len(values)), size=500)
    lead = np.array([r['lead_primary_confirmed'] == 'True' for r in events])
    anymatch = np.array([r['any_primary_confirmed'] == 'True' for r in events])
    flags = dict(multitrack=ntracks > 1, leading_unconfirmed=~lead,
                 any_primary_confirmed=anymatch, recovered_primary=~lead & anymatch)
    profiles = []
    for name, mask in masks.items():
        use = mask & available
        n = int(use.sum())
        den = draw @ use.astype(float)
        good = den > 0
        for metric, flag in flags.items():
            count = int((use & flag).sum())
            bs = (draw @ (use & flag).astype(float))[good] / den[good] * 100
            ci = np.quantile(bs, [.025, .975]) if len(bs) else [np.nan, np.nan]
            profiles.append(dict(scope=name, requested_N=int(mask.sum()), available_N=n,
                                 unavailable_N=int((mask & ~available).sum()), metric=metric, count=count,
                                 pct=100 * count / n if n else np.nan,
                                 conditional_low95_pct=float(ci[0]), conditional_high95_pct=float(ci[1]),
                                 valid_draws=int(good.sum()), source95='未测量', sparse=n < 20))
    table('X_profiles.tsv', profiles)
    # Independent count aggregation against the batch table, without using its masks.
    counts = Counter(int(r['row']) for r in nodes)
    edge_counts = Counter(int(r['row']) for r in pairs)
    for event in events:
        row = int(event['row'])
        if event['available'] == 'True':
            n = int(event['n_tracks'])
            assert counts[row] == n and edge_counts[row] == n * (n - 1) // 2
        else:
            assert counts[row] == edge_counts[row] == 0
    histogram = Counter(int(n) for n in ntracks[available])
    batch = next(r for r in read(OUT / 'profiles.tsv') if r['scope'] == 'all')
    expected = dict(available_N=int(available.sum()), candidate_tracks=len(nodes), pairs=len(pairs),
                    multitrack_N=sum(n for k, n in histogram.items() if k > 1),
                    leading_unconfirmed_N=int((available & ~lead).sum()),
                    recovered_primary_N=int((available & ~lead & anymatch).sum()))
    for k, value in expected.items():
        assert int(batch[k]) == value
    distribution = []
    for name in ['delta_x0_y0_mm', 'delta_calo_mm', 'delta_veto_mm', 'delta_slope']:
        a = np.array([float(r[name]) for r in pairs])
        valid = a[np.isfinite(a)]
        q = np.quantile(valid, [0, .25, .5, .75, 1]) if len(valid) else [np.nan] * 5
        distribution.append(dict(feature=name, total_pairs=len(a), finite_pairs=len(valid),
                                 minimum=q[0], p25=q[1], median=q[2], p75=q[3], maximum=q[4],
                                 unit='dimensionless' if name == 'delta_slope' else 'mm'))
    table('pair_distributions.tsv', distribution)
    finite_counts = {key: int(sum(np.isfinite(float(r[key])) for r in nodes))
                     for key in nodes[0] if key not in ['row', 'track_index', 'leading']}
    save('closeout_validation.json', dict(passed=True, **expected,
         candidate_count_histogram={str(k): v for k, v in sorted(histogram.items())},
         finite_candidate_fields=finite_counts, hitset_24bit_events=sum(r['hitset_24bit'] == 'True' for r in events),
         primary_matching_tracks=sum(r['primary_confirmed'] == 'True' for r in read(CACHE / 'truth_diagnostics.tsv')),
         source_event_payload_reads=0, new_fits=0, test_payload_records=0,
         original_X_boundaries='stage94 X_calo_groups.json / X_activity_groups.json; no refit or reselection',
         uncertainty='500 incoming draws conditional on frozen source/X quota; zero-success bootstrap is not a population upper bound',
         **cost(start)))


def oracle():
    """Small saved-table diagnostic with leading fallback; never a deployable input."""
    events = [r for r in read(CACHE / 'events.tsv') if r['available'] == 'True']
    labels = read(CACHE / 'truth_diagnostics.tsv')
    leading, best = [], []
    improved = 0
    for event in events:
        a = abs(float(event['lead_mu_log_error']))
        b = float(event['matched_candidate_oracle_abs_log_error'])
        value = min(a, b) if math.isfinite(b) else a
        improved += value < a - 1e-12
        leading.append(a * a)
        best.append(value * value)
    ratios = {}
    for name in ['all', 'primary_confirmed', 'not_primary_confirmed']:
        values = sorted(float(r['truth_hit_ratio']) for r in labels
                        if name == 'all' or (r['primary_confirmed'] == 'True') == (name == 'primary_confirmed'))
        q = np.quantile(values, [0, .25, .5, .75, 1])
        ratios[name] = dict(N=len(values), minimum=float(q[0]), p25=float(q[1]), median=float(q[2]),
                            p75=float(q[3]), maximum=float(q[4]), below_half_N=sum(v < .5 for v in values))
    save('muon_oracle_bound.json', dict(full_available_N=len(events),
         oracle_definition='per event min(abs(log(pz_leading/pz_true_mu)), abs(log(pz_truth_matched_candidate/pz_true_mu))); leading fallback if no match; no truth input deployable',
         leading_mu_pz_log_RMSE=math.sqrt(sum(leading) / len(leading)),
         leading_or_matched_oracle_mu_pz_log_RMSE=math.sqrt(sum(best) / len(best)),
         improved_incoming_N=improved, neutrino_energy_gain='未测量', truth_hit_ratio=ratios))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'report', 'oracle'])
    args = parser.parse_args()
    {'prepare': prepare_groups, 'report': main, 'oracle': oracle}[args.action]()
