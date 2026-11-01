#!/usr/bin/env python3
"""Post-test descriptive migration accounting; never selects a model or a cut."""
import argparse
import json
from pathlib import Path
import numpy as np
from frozen_evaluation import logs, read_cache, reportdir
from train_bdt import write_table


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--partition', choices=['test', 'challenge'], required=True)
    repo = Path(__file__).resolve().parents[1]
    a = p.parse_args()
    out = reportdir(repo)
    assert (out / f'{a.partition}_summary.json').exists()
    data = read_cache(repo, a.partition)
    state = json.loads((out / 'calibration_state.json').read_text())
    errors = {v: pred + state['offset_log'][v] - np.log(data['truth_E_GeV']) for v, pred in logs(data).items()}
    delta = errors['F5'] ** 2 - errors['F6'] ** 2
    reco_edges = [(100, 250), (250, 1000), (1000, np.inf)]
    true_edges = [(0, 100), (100, 250), (250, 1000), (1000, np.inf)]
    rows = []
    for lo, hi in reco_edges:
        reco = (data['reco_p_GeV'] >= lo) & (data['reco_p_GeV'] < hi)
        for primary in [True, False]:
            for low, high in true_edges:
                mask = (reco & (data['confirmed'] == primary) &
                        (data['primary_p_GeV'] >= low) & (data['primary_p_GeV'] < high))
                rows.append(dict(partition=a.partition, reco_p_low_GeV=lo, reco_p_high_GeV=hi,
                                 confirmed=primary, truth_p_low_GeV=low, truth_p_high_GeV=high,
                                 N=int(mask.sum()), source_groups=len(np.unique(data['group'][mask])),
                                 F5_log_RMSE=float(np.sqrt(np.mean(errors['F5'][mask] ** 2))) if mask.any() else np.nan,
                                 F6_log_RMSE=float(np.sqrt(np.mean(errors['F6'][mask] ** 2))) if mask.any() else np.nan,
                                 sum_log_squared_error_improvement=float(delta[mask].sum()),
                                 reco_bin_MSE_improvement_contribution=float(delta[mask].sum() / reco.sum())))
        np.testing.assert_allclose(sum(r['reco_bin_MSE_improvement_contribution'] for r in rows if r['reco_p_low_GeV'] == lo),
                                   np.mean(delta[reco]), atol=1e-12)
    write_table(out / f'{a.partition}_posthoc_migration.tsv', rows)


if __name__ == '__main__':
    main()
