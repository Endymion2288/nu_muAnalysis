"""Direct-primary deposit classes; never identify every secondary as a fake hit."""
import gzip
import json
import math
from collections import Counter
from pathlib import Path
import numpy as np
from stage158_finalize import gnu

ROOT=Path.cwd();OUT=ROOT/'workbook/stage192_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage192'
P=json.loads((OUT/'protocol.json').read_text())


def read(path):
    with gzip.open(path,'rt') as f:return json.load(f)


def write(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def classify(candidate,strips,unique):
    rows=[strips[s] for s in candidate['strips']]
    # Check unweighted barcode identity independently of validity/positive weight.
    barcodes={d['barcode'] for row in rows for d in row['deposits']}
    assert barcodes==set(candidate['contributors'])
    positive=[d for row in rows for d in row['deposits'] if d['weight']>0]
    if not unique or not all(r['present'] for r in rows) or not positive:
        return 'unknown'
    if not all(d['pointer_valid'] and d['pointer_in_selected_truth'] for d in positive):
        return 'unknown'
    flags=[d['pointer_is_unique_primary'] for d in positive]
    return 'pure_direct_primary' if all(flags) else 'mixed_direct_primary' if any(flags) else 'resolved_no_direct_primary'


def stats(values):
    a=np.asarray(values,float)
    return dict(N=len(a),RMS=float(np.sqrt(np.mean(a*a))) if len(a) else None,
        median=float(np.median(a)) if len(a) else None,abs95=float(np.quantile(abs(a),.95)) if len(a) else None,
        abs_le1_N=int((abs(a)<=1).sum()),abs_le3_N=int((abs(a)<=3).sum()))


def summarize(phase):
    old={(r['case']['source_index'],r['case']['entry']):r for r in read(ROOT/P['original_predictions'])['records']}
    data=read(CACHE/f'{phase}_native.json.gz');groups=[];all_checks=0
    for source in P['sources']:
        records=[r for r in data['records'] if r['case']['source_index']==source['index']]
        classes={q:[] for q in ['pure_direct_primary','mixed_direct_primary','resolved_no_direct_primary','unknown']}
        residual={q:[] for q in classes};primary_N=0;matched_N=0;has_primary_fit=0;foreign=0;invalid=0;unknown_reasons=Counter()
        lowpz_N=0;lowpz_matched_N=0
        for r in records:
            c=r['case'];previous=old[(c['source_index'],c['entry'])];m=previous['measurement']
            assert (c['run'],c['event'])==(previous['case']['reference']['run'],previous['case']['reference']['event'])
            links=r['links'];unique=len(links['primary_muons'])==1
            primary_N+=unique
            rows={v['strip']:v for v in links['strips']}
            for row in rows.values():
                for d in row['deposits']:
                    invalid+=not d['pointer_valid'];foreign+=d['pointer_valid'] and not d['pointer_in_selected_truth']
                    assert not d['pointer_is_unique_primary'] or d['pointer_valid'] and d['pointer_in_selected_truth'] and unique
            if unique and m['leading']:
                bc=links['primary_muons'][0]['barcode']
                has_primary_fit+=any(b==bc and n>0 for b,n in m['leading']['barcode_cluster_counts'])
            eligible=previous['original_leading_match'] and m['start_supported']
            matched_N+=eligible
            pz=previous['case']['reference']['pz0_GeV']
            lowpz=pz is not None and 50<=pz<100
            lowpz_N+=lowpz;lowpz_matched_N+=lowpz and eligible
            for w in m['wafers']:
                for candidate in w['candidates']:
                    label=classify(candidate,rows,unique);all_checks+=1
                    if eligible and w['success'] and w['inside_geometric_bounds'] and candidate.get('pull') is not None:
                        classes[label].append(candidate['pull']);residual[label].append(candidate['residual_mm'])
                        if label=='unknown':
                            sd=[rows[s] for s in candidate['strips']]
                            pos=[v for row in sd for v in row['deposits'] if v['weight']>0]
                            for reason,flag in [('primary_graph_not_unique',not unique),('some_strip_SDO_absent',any(not row['present'] for row in sd)),
                                ('no_positive_stored_deposit',not pos),('invalid_positive_pointer',any(not v['pointer_valid'] for v in pos)),
                                ('foreign_positive_pointer',any(v['pointer_valid'] and not v['pointer_in_selected_truth'] for v in pos)),
                                ('known_primary_positive_also_present',any(v['pointer_is_unique_primary'] for v in pos))]:
                                if flag:unknown_reasons[reason]+=1
        groups.append(dict(label=source['label'],parents_N=len(records),unique_primary_graph_N=primary_N,
            original_matched_supported_N=matched_N,any_primary_barcode_in_fitted_contributors_N=has_primary_fit,
            original_pz50_100_N=lowpz_N,matched_supported_pz50_100_N=lowpz_matched_N,
            invalid_deposits_N=invalid,foreign_truth_pointer_deposits_N=foreign,
            unknown_reason_flags_N=dict(unknown_reasons),unknown_reason_flags_overlap=True,
            pull={q:stats(v) for q,v in classes.items()},residual_mm={q:stats(v) for q,v in residual.items()}))
    result=dict(groups=groups,cached_actual_SDO_contributor_checks_N=all_checks,
        label_limit='Truth graph/direct positive deposit class; not necessarily an exclusive correct muon hit. No-direct-primary can be a physical secondary/delta ray. Conditional measured cluster pulls are not unconditional covariance coverage or a data association error rate.',
        promotion=False,overall_complete=False)
    write(f'{phase}_prediction_summary.json',result)
    return data,result


if __name__=='__main__':
    import sys
    phase=sys.argv[1];data,summary=summarize(phase)
    if phase=='pilot':
        native=json.loads((OUT/'pilot_native_summary.json').read_text())
        complete=max(gnu(f)['CPU_s'] for f in OUT.glob('pilot*_time.txt'))+max(gnu(f)['CPU_s'] for f in OUT.glob('pilot*_compile_time.txt'))
        projection=3*(complete+160*native['slowest_postfirst_execute_CPU_s'])
        supported=[g['unique_primary_graph_N']>0 and g['pull']['pure_direct_primary']['N']+g['pull']['mixed_direct_primary']['N']>0 for g in summary['groups']]
        physical=supported[0] and any(supported[1:])
        used=json.loads((OUT/'scheduler_accounting.json').read_text())['total_CPU_s']
        admitted=bool(physical and projection<=600 and used+projection+200<=1200 and native['RSS_KiB']*1.25/1024<=12000)
        write('admission.json',dict(admitted=admitted,physical_support=physical,projection_CPU_s=projection,full_cap_CPU_s=600,
            complete_pilot_compile_CPU_s=complete,slowest_postfirst_CPU_s=native['slowest_postfirst_execute_CPU_s'],
            used_CPU_s=used,audit_reserve_CPU_s=200,overall_complete=False))
        print('ADMISSION',admitted,projection,physical,flush=True)
