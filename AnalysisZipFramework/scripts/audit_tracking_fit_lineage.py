#!/usr/bin/env python3
"""Summarize diagnostic fit stages and compare measured hit identifiers exactly."""
import argparse
import csv
import json
from pathlib import Path
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows, hitsets = [], {}
    for path in sorted(args.input.glob('*/*.tar.gz')):
        if path.parent.name not in ['controls', 'loss_targets', 'seedstarts']:
            continue
        job = path.parent.name + '/' + path.name[:3]
        with tarfile.open(path) as archive:
            config = json.load(archive.extractfile('effective_reco.json'))
            for name in archive.getnames():
                if not name.startswith('CKF'):
                    continue
                records = [json.loads(line) for line in archive.extractfile(name)]
                for stage in ['found', 'selected_isolated', 'refit_acts', 'refit_result']:
                    for record in [r for r in records if r['stage'] == stage]:
                        # Found branches share a seed ID. Their state blocks follow
                        # each branch header; do not group them by the seed alone.
                        start = records.index(record) + 1
                        states = []
                        refs = []
                        for r in records[start:]:
                            if r['stage'] == stage + '_reference':
                                refs.append(r)
                                continue
                            if r['stage'] != stage + '_state':
                                break
                            states.append(r)
                        hits = tuple(sorted(r['hit'] for r in states if 'hit' in r
                                            and r.get('measurement', True)))
                        positions = [r['surface'][0][3] for r in states if 'surface' in r
                                     and r.get('measurement')]
                        qop = refs[0]['bound'][4] if refs else None
                        key = (job, name, stage)
                        hitsets[key] = hits
                        rows.append(dict(job=job, control=config['control'], collection=name,
                            stage=stage, candidate=record['candidate'],
                            measurements=record.get('nMeasurements', record.get('measurements')),
                            chi2=record.get('chi2'), ndof=record.get('ndof'),
                            reference_qop_gev_inverse=qop, hits=len(hits),
                            longitudinal_min_mm=min(positions) if positions else None,
                            longitudinal_max_mm=max(positions) if positions else None))
    comparisons = []
    for (job, collection, stage), hits in hitsets.items():
        if job.startswith('seedstarts/') and stage in ['selected_isolated', 'refit_acts', 'refit_result']:
            reference = hitsets.get(('seedstarts/000', collection, stage), ())
            comparisons.append(dict(job=job, collection=collection, stage=stage,
                reference_hits=len(reference), hits=len(hits), exact_hits=(hits == reference),
                common_hits=len(set(hits) & set(reference))))
    for name, data in [('fit_stages', rows), ('seedstart_hit_closure', comparisons)]:
        with (args.output / (name + '.tsv')).open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]), delimiter='\t', lineterminator='\n')
            writer.writeheader()
            writer.writerows(data)


if __name__ == '__main__':
    main()
