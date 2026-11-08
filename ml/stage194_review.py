"""Fitted-cluster truth support, with original IFT residual ledger unchanged."""
import csv,gzip,json,math
from collections import Counter
from pathlib import Path
from stage192_review import classify
from stage158_finalize import gnu
ROOT=Path.cwd();OUT=ROOT/'workbook/stage194_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage194'
P=json.loads((OUT/'protocol.json').read_text());CLASSES=['pure_direct_primary','mixed_direct_primary','resolved_no_direct_primary','unknown']
def read(path):
 with gzip.open(ROOT/path,'rt') as f:return json.load(f)
def write(name,value):(OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def table(name,rows):
 with (OUT/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
def prepare(phase):
 data=read(CACHE.relative_to(ROOT)/f'{phase}_native.json.gz')
 old={(r['case']['source_index'],r['case']['entry']):r for r in read(P['original_predictions'])['records']}
 previous={(r['case']['source_index'],r['case']['entry']):r for r in read('ntuples/energy_ml_stage192/full_native.json.gz')['records']}
 rows=[];checks=0
 for rec in data['records']:
  c=rec['case'];key=(c['source_index'],c['entry']);before=old[key];m=before['measurement'];fit=rec['fit'];links=rec['links'];unique=len(links['primary_muons'])==1
  assert (c['run'],c['event'])==(before['case']['reference']['run'],before['case']['reference']['event'])
  assert links['primary_muons']==previous[key]['links']['primary_muons']
  if m['leading']:
   assert fit['leading']=={k:m['leading'][k] for k in ['collection_index','pz0_GeV','charge']}
   assert fit['barcode_cluster_counts']==m['leading']['barcode_cluster_counts']
  else:assert fit['leading'] is None
  strips={r['strip']:r for r in links['strips']};counts=Counter();reasons=Counter();any_primary=0
  aggregate=Counter()
  for cluster in fit['clusters']:
   if not cluster['PRD_present'] or not cluster['strips']:
    label='unknown';reasons['missing_PRD_or_empty_strips']+=1
   else:
    label=classify(cluster,strips,unique);checks+=1
    for b in cluster['contributors']:aggregate[b]+=1
   pos=[d for s in cluster['strips'] for d in strips[s]['deposits'] if d['weight']>0]
   any_primary+=any(d['pointer_is_unique_primary'] for d in pos)
   if any(not strips[s]['present'] for s in cluster['strips']):reasons['some_strip_SDO_absent']+=1
   if not pos:reasons['no_positive_stored_deposit']+=1
   if any(not d['pointer_valid'] for d in pos):reasons['invalid_positive_pointer']+=1
   if any(d['pointer_valid'] and not d['pointer_in_selected_truth'] for d in pos):reasons['foreign_positive_pointer']+=1
   counts[label]+=1
  assert sorted([b,n] for b,n in aggregate.items())==fit['barcode_cluster_counts']
  assert sum(counts.values())==len(fit['clusters'])
  prevstrips={r['strip']:r for r in previous[key]['links']['strips']};values=[]
  if before['original_leading_match'] and m['start_supported']:
   for w in m['wafers']:
    if w['success'] and w['inside_geometric_bounds']:
     for a in w['candidates']:
      if a.get('pull') is not None and classify(a,prevstrips,unique)=='pure_direct_primary':values.append(a['pull'])
  group=('graph_unknown' if not unique else 'no_fitted_track' if fit['leading'] is None else 'direct_primary_positive_pointer' if any_primary else 'no_direct_primary_positive_pointer')
  q=dict(source=c['label'],source_index=c['source_index'],entry=c['entry'],run=c['run'],event=c['event'],
   matched_supported=bool(before['original_leading_match'] and m['start_supported']),fit_group=group,
   fitted_clusters_N=len(fit['clusters']),known_primary_positive_clusters_N=any_primary,
   all_fit_clusters_resolved_without_primary=bool(fit['clusters'] and counts['resolved_no_direct_primary']==len(fit['clusters'])),
   **{k+'_fit_clusters_N':counts[k] for k in CLASSES},**{k:reasons[k] for k in ['missing_PRD_or_empty_strips','some_strip_SDO_absent','no_positive_stored_deposit','invalid_positive_pointer','foreign_positive_pointer']},
   IFT_pure_primary_candidates_N=len(values),IFT_pure_primary_pull2=math.fsum(v*v for v in values))
  rows.append(q)
 groups=[]
 for s in P['sources']:
  total=math.fsum(r['IFT_pure_primary_pull2'] for r in rows if r['source_index']==s['index'])
  for key in ['all','graph_unknown','no_fitted_track','direct_primary_positive_pointer','no_direct_primary_positive_pointer']:
   parents=[r for r in rows if r['source_index']==s['index'] and (key=='all' or r['fit_group']==key)]
   n=sum(r['IFT_pure_primary_candidates_N'] for r in parents);ss=math.fsum(r['IFT_pure_primary_pull2'] for r in parents)
   groups.append(dict(source=s['label'],fit_group=key,parents_N=len(parents),matched_supported_parents_N=sum(r['matched_supported'] for r in parents),
    fitted_clusters_N=sum(r['fitted_clusters_N'] for r in parents),known_primary_positive_clusters_N=sum(r['known_primary_positive_clusters_N'] for r in parents),
    all_fit_clusters_resolved_without_primary_parents_N=sum(r['all_fit_clusters_resolved_without_primary'] for r in parents),
    **{k+'_fit_clusters_N':sum(r[k+'_fit_clusters_N'] for r in parents) for k in CLASSES},
    some_strip_SDO_absent=sum(r['some_strip_SDO_absent'] for r in parents),IFT_candidates_N=n,IFT_pull2_sum=ss,
    IFT_pull_RMS=math.sqrt(ss/n) if n else None,IFT_pull2_fraction=ss/total if total else None))
 result=dict(passed=True,N=len(rows),fitted_contributor_checks_N=checks,groups=groups,limits='Positive direct fit-cluster pointers/completeness, not track identity certification or data misassociation/coverage.',overall_complete=False,promotion=False)
 table(f'{phase}_parents.tsv',rows);write(f'{phase}_prediction_summary.json',result)
 return data,rows,result
if __name__=='__main__':
 import sys
 phase=sys.argv[1];data,rows,result=prepare(phase)
 if phase=='pilot':
  native=json.loads((OUT/'pilot_native_summary.json').read_text());complete=gnu(OUT/'pilot_time.txt')['CPU_s']+gnu(OUT/'pilot_compile_time.txt')['CPU_s']
  projection=3*(complete+160*native['slowest_postfirst_execute_CPU_s'])
  supports=[any(r['known_primary_positive_clusters_N']>0 for r in rows if r['source_index']==s['index']) for s in P['sources']]
  used=json.loads((OUT/'scheduler_accounting.json').read_text())['total_CPU_s']
  write('admission.json',dict(admitted=bool(supports[0] and any(supports[1:]) and projection<=600 and used+projection+200<=1200 and native['RSS_KiB']*1.25/1024<=12000),
   projection_CPU_s=projection,complete_pilot_compile_CPU_s=complete,slowest_postfirst_CPU_s=native['slowest_postfirst_execute_CPU_s'],supports=supports,used_CPU_s=used,overall_complete=False))
  print('ADMISSION',projection,supports,flush=True)
