"""Batch-only fixed summaries and measured-cost admission; never choose nearest hit."""
import csv
import gzip
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from stage158_finalize import gnu

ROOT = Path.cwd()
OUT = ROOT / 'workbook/stage190_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage190'
P = json.loads((OUT / 'protocol.json').read_text())


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def stats(values):
    a = np.asarray(values, dtype=float)
    return dict(N=len(a), mean=float(a.mean()) if len(a) else None,
        RMS=float(np.sqrt(np.mean(a*a))) if len(a) else None,
        median=float(np.median(a)) if len(a) else None,
        abs95=float(np.quantile(abs(a), .95)) if len(a) else None,
        abs_gt3_N=int((abs(a)>3).sum()))


def summarize(phase):
    with gzip.open(CACHE / f'{phase}_native.json.gz', 'rt') as f:
        data = json.load(f)
    groups, rows = [], []
    for source in P['sources']:
        records = [r for r in data['records'] if r['case']['label'] == source['label']]
        pull, residual, noMatSigma, all_rows, sharedPull, unsharedPull = [], [], [], [], [], []
        for record in records:
            m, c = record['measurement'], record['case']
            if not record['original_leading_match'] or not m['start_supported']:
                rows.append(dict(label=c['label'], entry=c['entry'], matched=record['original_leading_match'], supported=False,
                    wafer='NA', inside='NA', candidates='NA', compatible3='NA', SDO=m['SDO_present']))
                continue
            assert 0 not in m['leading']['fitted_stations']
            fitted_contributors={b for b,n in m['leading']['barcode_cluster_counts']}
            for w in m['wafers']:
                if not w['success']:
                    rows.append(dict(label=c['label'], entry=c['entry'], matched=True, supported=False,
                        wafer=w['wafer'], inside='NA', candidates=len(w['candidates']), compatible3='NA', SDO=m['SDO_present']))
                    continue
                candidates = [a for a in w['candidates'] if a.get('pull') is not None]
                inside = w['inside_geometric_bounds']
                row = dict(label=c['label'], entry=c['entry'], matched=True, supported=True, wafer=w['wafer'],
                    inside=inside, candidates=len(w['candidates']), compatible3=sum(abs(a['pull'])<=3 for a in candidates), SDO=m['SDO_present'])
                rows.append(row)
                all_rows.append(row)
                if inside:
                    pull.extend(a['pull'] for a in candidates)
                    residual.extend(a['residual_mm'] for a in candidates)
                    if m['SDO_present'] and fitted_contributors:
                        for a in candidates:
                            (sharedPull if fitted_contributors.intersection(a['contributors']) else unsharedPull).append(a['pull'])
                    if w.get('no_material') and w['covariance'] and w['no_material']['covariance']:
                        v, v0 = w['covariance'][0][0], w['no_material']['covariance'][0][0]
                        if v is not None and v0 is not None and v0>0 and v>=0:
                            noMatSigma.append(math.sqrt(v/v0))
        active = [r for r in all_rows if r['inside']]
        groups.append(dict(label=source['label'], parents_N=len(records), original_leading_matched_N=sum(r['original_leading_match'] for r in records),
            start_supported_N=sum(r['measurement']['start_supported'] for r in records),
            matched_start_N=sum(r['original_leading_match'] and r['measurement']['start_supported'] for r in records),
            matched_pz50_100_N=sum(r['original_leading_match'] and r['measurement']['leading'] is not None and 50<=r['measurement']['leading']['pz0_GeV']<100 for r in records),
            start_reasons=dict(Counter(r['measurement']['reason'] for r in records)),
            source_propagation_roundtrip_success_N=sum(r['measurement'].get('source',{}).get('propagation_roundtrip_success',False) for r in records),
            wafer_propagation_failed_N=sum(not w['success'] for r in records for w in r['measurement']['wafers']),
            successful_wafer_predictions_N=len(all_rows), inside_geometric_wafer_predictions_N=len(active),
            geometric_no_cluster_N=sum(r['candidates']==0 for r in active),
            multi_candidate_wafer_N=sum(r['candidates']>1 for r in active),
            compatible3_zero_N=sum(r['compatible3']==0 for r in active), compatible3_multiple_N=sum(r['compatible3']>1 for r in active),
            SDO_parent_N=sum(r['measurement']['SDO_present'] for r in records),
            all_candidate_residual_mm=stats(residual), all_candidate_pull=stats(pull),
            SDO_shared_with_fit_contributor_pull=stats(sharedPull),SDO_no_shared_fit_contributor_pull=stats(unsharedPull),
            material_over_no_material_sigma_ratio=stats(noMatSigma)))
    write(f'{phase}_prediction_summary.json', dict(groups=groups,
        scope='All candidates on geometrically intersected wafers; correlated/shared PRD observations, not independent events or calibrated pull coverage. No nearest-hit selection. Geometry-only absence is not a certified masked-detector hole.',
        association_error_rate=None, independent_real_control_coverage=None, new_energy_performance=None,
        SDO_note='Shared-contributor diagnostic only, not a certified primary-muon label or wrong-association rate. No truth enters deployed features.',
        promotion=False, overall_complete=False))
    with (OUT / f'{phase}_wafer_support.tsv').open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    return data, groups


def main():
    import sys
    phase = sys.argv[1]
    data, groups = summarize(phase)
    if phase != 'pilot':
        return
    native = json.loads((OUT / 'pilot_native_summary.json').read_text())
    times = [gnu(p) for p in OUT.glob('pilot*_time.txt')]
    complete_cpu = max(t['CPU_s'] for t in times) + max((gnu(p)['CPU_s'] for p in OUT.glob('pilot*_compile_time.txt')), default=0.)
    event_cpu = max(r['execute_CPU_s'] for r in data['records'][1:])
    # Conservatively charge complete pilot initialization and the slowest measured event for all160.
    projection = 3 * (complete_cpu + 64*event_cpu)
    support = (groups[0]['matched_start_N']>0 and groups[0]['inside_geometric_wafer_predictions_N']>0 and groups[0]['all_candidate_pull']['N']>0)
    used = json.loads((OUT / 'scheduler_accounting.json').read_text())['total_CPU_s']
    admitted = bool(support and projection<=600 and used+projection+200<=1200 and native['RSS_KiB']/1024*1.25<=8000)
    write('admission.json', dict(admitted=admitted, physical_support=support, complete_native_CPU_s=complete_cpu,
        slowest_nonfirst_execute_CPU_s=event_cpu, conservative_full_CPU_projection_s=projection, full_cap_CPU_s=600,
        scheduler_used_before_review_CPU_s=used, audit_reserve_CPU_s=200, stage_budget_CPU_s=1200,
        projected_RSS_MB=native['RSS_KiB']/1024*1.25,
        limit='Not a performance claim or a controlled speedup; all geometry, match failures and original parents retained.'))
    print('ADMISSION', admitted, projection, support, flush=True)


if __name__ == '__main__':
    main()
