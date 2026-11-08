"""Different scalar implementation of the complete parent/deposit partition."""
from stage193_common import *

old={(r['case']['source_index'],r['case']['entry']):r for r in read(P['inputs'][0])['records']}
full=read(P['inputs'][1])['records'];saved=read('ntuples/energy_ml_stage193/full_parents.json.gz')
assert len(full)==len(saved)==160
independent_checks=0;maxdiff=0.
for r,q in zip(full,saved):
 c=r['case'];m=old[(c['source_index'],c['entry'])]['measurement'];p=r['links']['primary_muons']
 assert (c['source_index'],c['entry'],c['run'],c['event'])==(q['source_index'],q['entry'],q['run'],q['event'])
 counts=dict(m['leading']['barcode_cluster_counts']) if m['leading'] else {}
 bc=p[0]['barcode'] if len(p)==1 else None
 expected=('graph_unknown' if len(p)!=1 else 'no_fitted_track' if not m['leading'] else 'no_primary_fit_barcode' if counts.get(bc,0)<=0
  else 'primary_and_other_fit_barcodes' if sum(n for b,n in counts.items() if b!=bc)>0 else 'primary_only_stored_fit_barcodes')
 assert q['category']==expected and q['primary_fit_cluster_contribution_N']==counts.get(bc,0)
 strips={s['strip']:s for s in r['links']['strips']};values={k:[] for k in CLASSES}
 if q['matched'] and q['start_supported']:
  for w in m['wafers']:
   if not(w['success'] and w['inside_geometric_bounds']):continue
   for a in w['candidates']:
    if a.get('pull') is None:continue
    sd=[strips[s] for s in a['strips']];positive=[d for s in sd for d in s['deposits'] if d['weight']>0]
    known=(len(p)==1 and all(s['present'] for s in sd) and len(positive)>0 and all(d['pointer_valid'] and d['pointer_in_selected_truth'] for d in positive))
    primary=sum(bool(d['pointer_is_unique_primary']) for d in positive)
    label=('unknown' if not known else 'pure_direct_primary' if primary==len(positive) else 'mixed_direct_primary' if primary>0 else 'resolved_no_direct_primary')
    values[label].append((a['pull'],a['residual_mm']))
 for label,v in values.items():
  obs=q['classes'][label];assert obs['N']==len(v) and obs['abs_pull_gt3_N']==len([a for a,b in v if abs(a)>3])
  for key,expected_value in [('pull2',sum(a*a for a,b in v)),('residual2_mm2',sum(b*b for a,b in v))]:
   delta=abs(expected_value-obs[key]);assert math.isclose(expected_value,obs[key],rel_tol=1e-12,abs_tol=1e-10);maxdiff=max(maxdiff,delta);independent_checks+=1
pilot=read('ntuples/energy_ml_stage193/pilot_parents.json.gz');lookup={(r['source_index'],r['entry']):r for r in saved}
assert len(pilot)==16 and all(r==lookup[(r['source_index'],r['entry'])] for r in pilot)
account=json.loads((OUT/'full_accounting.json').read_text());baseline=json.loads((ROOT/'workbook/stage192_energy_ml/full_prediction_summary.json').read_text())
for g in baseline['groups']:
 for label in CLASSES:
  row=next(v for v in account['groups'] if v['source']==g['label'] and v['deposit_class']==label and v['fit_support_category']=='all')
  v=g['pull'][label];assert row['candidates_N']==v['N']
  assert row['pull_RMS'] is None and v['RMS'] is None or math.isclose(row['pull_RMS'],v['RMS'],rel_tol=1e-12,abs_tol=1e-12)
  pieces=[v for v in account['groups'] if v['source']==g['label'] and v['deposit_class']==label and v['fit_support_category']!='all']
  assert sum(v['parents_N'] for v in pieces)==g['parents_N']
  assert sum(v['candidates_N'] for v in pieces)==row['candidates_N']
  assert math.isclose(math.fsum(v['pull2_sum'] for v in pieces),row['pull2_sum'],rel_tol=1e-12,abs_tol=1e-10)
write('independent_validation.json',dict(passed=True,all160_parents_retained=True,independent_scalar_checks_N=independent_checks,
 max_absolute_square_sum_difference=maxdiff,pilot_full_exact_N=16,Stage192_all_class_counts_RMS_reproduced=True,all_category_partitions_closed=True,
 limitation='Independent scalar accounting of cached labels; no new fitted-cluster pointer or SDO-completeness measurement, no data association certification.',overall_complete=False))
print('AUDIT PASSED',independent_checks,flush=True)
