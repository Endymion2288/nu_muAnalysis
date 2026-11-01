#!/usr/bin/env python3
"""Package only the next allowed held-out partition for stage34 Condor inference."""
import argparse
import shutil
import tarfile
from pathlib import Path
from frozen_evaluation import configuration, manifest, reportdir


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--partition', required=True, choices=['calibration', 'test', 'challenge'])
    a = p.parse_args()
    cfg = configuration(a.repo)
    if a.partition == 'test':
        assert (reportdir(a.repo) / 'calibration_state.json').exists()
    if a.partition == 'challenge':
        assert (reportdir(a.repo) / 'test_summary.json').exists()
    rows = manifest(a.repo)
    groups = {part: {r['group'] for r in rows if r['partition'] == part} for part in ['train', 'validation'] + cfg['order']}
    for i, part in enumerate(groups):
        for other in list(groups)[i + 1:]:
            assert not groups[part] & groups[other]
    paths = [f'ml/{s}.py' for s in ['frozen_evaluation', 'track_response', 'train_bdt']]
    paths += ['ml/configs/' + s for s in ['baseline.yaml', 'track_response.yaml', 'frozen_evaluation.yaml', 'files.tsv']]
    paths += [s.format(seed=i) for s in cfg['models'].values() for i in cfg['seed_indices']]
    paths += [f'ntuples/energy_ml_stage12/dataset/{a.partition}.npz']
    for name in ['calibration_state.json', 'test_summary.json']:
        if (reportdir(a.repo) / name).exists():
            paths.append('workbook/stage34_energy_ml/' + name)
    payload = a.repo / f'software/energy-ml-frozen-stage34-{a.partition}.tar.gz'
    with tarfile.open(payload, 'w:gz') as archive:
        for path in paths:
            archive.add(a.repo / path, arcname=path)
    spool = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage34')
    (spool / 'logs').mkdir(parents=True, exist_ok=True)
    shutil.copy2(a.repo / 'AnalysisZipFramework/submission/run_ml_frozen_evaluation.sh', spool)
    (spool / 'run_ml_frozen_evaluation.sh').chmod(0o755)
    (a.repo / 'ntuples/energy_ml_stage34/shards').mkdir(parents=True, exist_ok=True)
    print(dict(partition=a.partition, payload=str(payload), bytes=payload.stat().st_size,
               jobs=(sum(r['partition'] == a.partition for r in rows) + cfg['batch_size'] - 1) // cfg['batch_size'],
               disjoint_source_groups_verified=True))


if __name__ == '__main__':
    main()
