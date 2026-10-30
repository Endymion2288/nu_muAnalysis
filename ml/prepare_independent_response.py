#!/usr/bin/env python3
"""Build and byte-verify a small stage27 source/input payload for Condor."""
import argparse
import json
import tarfile
from pathlib import Path

from independent_response import config


def main():
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--audit',action='store_true');args=parser.parse_args()
    root = Path(__file__).resolve().parents[1]; cfg = config(root)
    paths = ['ml/closure.py', 'ml/within_response.py', 'ml/profile_response.py', 'ml/source_response.py',
             'ml/independent_response.py', 'ml/run_independent_response.py', 'ml/configs/closure.yaml',
             'ml/configs/within_response.yaml', 'ml/configs/profile_response.yaml', 'ml/configs/independent_response.yaml',
             'workbook/stage23_energy_ml/folds.tsv', 'ntuples/energy_ml_stage12/dataset/validation.npz']
    paths += [s['path'] for s in cfg['models'].values() if 'path' in s]
    if args.audit:
        jobs=[]
        report=root/'workbook/stage27_energy_ml'
        runs=[json.loads(p.read_text()) for p in sorted(report.glob('*/seed_*/alpha_*/summary.json'))]
        if not runs and (report/'summary.json').exists(): runs=list(json.loads((report/'summary.json').read_text())['runs'].values())
        for r in runs:
            if r['numerical_stats']['solver_failures']:
                jobs.append((r['model'],r['seed'],r['alpha_index']))
                paths.append(f"ml/artifacts/stage27/{r['model']}/seed_{r['seed']}/alpha_{r['alpha_index']}/independent_inference.npz")
        assert jobs
        paths+=['ml/audit_independent_starts.py','ml/check_profile_response.py']
        spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage27')
        (spool/'start_audit_jobs.tsv').write_text(''.join(f'{m} {s} {a}\n' for m,s,a in jobs))
        (root/'workbook/stage27_energy_ml/start_audit_plan.json').write_text(json.dumps(dict(jobs=jobs,purpose='Explain unsuccessful SLSQP starts; production arrays and physics budget unchanged.'),indent=2)+'\n')
    payload = root / ('software/energy-ml-independent-audit-stage27.tar.gz' if args.audit else 'software/energy-ml-independent-stage27.tar.gz')
    with tarfile.open(payload, 'w:gz') as tar:
        for name in paths: tar.add(root/name, arcname=name)
    with tarfile.open(payload, 'r:gz') as tar:
        for name in paths: assert tar.extractfile(name).read() == (root/name).read_bytes()
    print(json.dumps(dict(payload=str(payload), bytes=payload.stat().st_size, members=paths, byte_verified=True)))


if __name__ == '__main__': main()
