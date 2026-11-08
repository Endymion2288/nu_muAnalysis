"""Exact fit payload/parent overlap and independent positive-pointer partition."""
from stage194_review import *
if __name__=='__main__':
 data,rows,summary=prepare('full');assert len(rows)==160
 pilot=read('ntuples/energy_ml_stage194/pilot_native.json.gz')['records']
 lookup={(r['case']['source_index'],r['case']['entry']):r for r in data['records']};checks=0
 for r in pilot:
  f=lookup[(r['case']['source_index'],r['case']['entry'])];assert r['links']==f['links'] and r['fit']==f['fit']
 assert len(pilot)==16
 for r,q in zip(data['records'],rows):
  strips={s['strip']:s for s in r['links']['strips']};counts={k:0 for k in CLASSES};anydirect=0
  for c in r['fit']['clusters']:
   sd=[strips[s] for s in c['strips']];pos=[v for s in sd for v in s['deposits'] if v['weight']>0]
   direct=sum(bool(v['pointer_is_unique_primary']) for v in pos);anydirect+=direct>0
   known=(len(r['links']['primary_muons'])==1 and c['PRD_present'] and len(sd)>0 and all(s['present'] for s in sd) and len(pos)>0 and all(v['pointer_valid'] and v['pointer_in_selected_truth'] for v in pos))
   label='unknown' if not known else 'pure_direct_primary' if direct==len(pos) else 'mixed_direct_primary' if direct>0 else 'resolved_no_direct_primary'
   counts[label]+=1;checks+=1
  assert all(counts[k]==q[k+'_fit_clusters_N'] for k in CLASSES)
  assert anydirect==q['known_primary_positive_clusters_N']
  assert q['all_fit_clusters_resolved_without_primary']==bool(r['fit']['clusters'] and counts['resolved_no_direct_primary']==len(r['fit']['clusters']))
 prev=json.loads((ROOT/'workbook/stage192_energy_ml/full_prediction_summary.json').read_text())
 for g in prev['groups']:
  r=next(r for r in summary['groups'] if r['source']==g['label'] and r['fit_group']=='all');old=g['pull']['pure_direct_primary']
  assert r['parents_N']==g['parents_N'] and r['IFT_candidates_N']==old['N']
  assert math.isclose(r['IFT_pull_RMS'],old['RMS'],rel_tol=1e-12)
 write('independent_validation.json',dict(passed=True,N=160,pilot_full_exact_N=16,fitted_cluster_class_checks_N=checks,
  exact_original_leading_pz_charge_and_unweighted_barcode_counts=True,all_Stage192_pure_primary_IFT_counts_RMS_reproduced=True,
  limits='Structural and scalar audit, not an independent HepMC resolver, SDO detection-efficiency or fitted-track truth certification.',overall_complete=False,promotion=False))
 print('AUDIT PASSED',checks,flush=True)
