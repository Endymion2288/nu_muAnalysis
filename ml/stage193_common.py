"""Cached mechanism accounting; scientific execution only on Condor."""
import csv,gzip,json,math,resource,time
from collections import defaultdict
from pathlib import Path
from stage192_review import classify
ROOT=Path.cwd();OUT=ROOT/'workbook/stage193_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage193'
P=json.loads((OUT/'protocol.json').read_text())
CLASSES=['pure_direct_primary','mixed_direct_primary','resolved_no_direct_primary','unknown']
def read(path):
 with gzip.open(ROOT/path,'rt') as f:return json.load(f)
def write(name,value): (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def table(name,rows):
 with (OUT/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
def category(m,links):
 if len(links['primary_muons'])!=1:return 'graph_unknown'
 if not m['leading']:return 'no_fitted_track'
 bc=links['primary_muons'][0]['barcode'];counts=dict(m['leading']['barcode_cluster_counts'])
 if counts.get(bc,0)==0:return 'no_primary_fit_barcode'
 return 'primary_and_other_fit_barcodes' if any(n>0 for b,n in counts.items() if b!=bc) else 'primary_only_stored_fit_barcodes'
def build(phase):
 old=read(P['inputs'][0])['records'];links=read(P['inputs'][2 if phase=='pilot' else 1])['records']
 old={(r['case']['source_index'],r['case']['entry']):r for r in old};rows=[];slowest=0
 for rec in links:
  tick=time.process_time();c=rec['case'];key=(c['source_index'],c['entry']);r=old[key];m=r['measurement'];lk=rec['links'];primary=lk['primary_muons'];bc=primary[0]['barcode'] if len(primary)==1 else None
  assert (c['run'],c['event'])==(r['case']['reference']['run'],r['case']['reference']['event'])
  counts=dict(m['leading']['barcode_cluster_counts']) if m['leading'] else {}
  strip={v['strip']:v for v in lk['strips']}
  q=dict(source=c['label'],source_index=c['source_index'],entry=c['entry'],run=c['run'],event=c['event'],
   pz0_GeV=r['case']['reference']['pz0_GeV'],matched=bool(r['original_leading_match']),start_supported=bool(m['start_supported']),
   category=category(m,lk),primary_barcode=bc,primary_fit_cluster_contribution_N=counts.get(bc,0),
   max_other_fit_cluster_contribution_N=max([n for b,n in counts.items() if b!=bc],default=0),stored_fit_contributor_barcodes_N=len(counts),
   classes={k:dict(N=0,pull2=0.,residual2_mm2=0.,abs_pull_gt3_N=0,max_abs_pull=None) for k in CLASSES})
  accum={k:[] for k in CLASSES}
  if q['matched'] and q['start_supported']:
   for w in m['wafers']:
    if not (w['success'] and w['inside_geometric_bounds']):continue
    for a in w['candidates']:
     if a.get('pull') is None:continue
     label=classify(a,strip,len(primary)==1);accum[label].append((a['pull'],a['residual_mm']))
  for k,values in accum.items():
   q['classes'][k]=dict(N=len(values),pull2=math.fsum(a*a for a,b in values),residual2_mm2=math.fsum(b*b for a,b in values),
    abs_pull_gt3_N=sum(abs(a)>3 for a,b in values),max_abs_pull=max([abs(a) for a,b in values],default=None))
  rows.append(q);slowest=max(slowest,time.process_time()-tick)
 assert len(rows)==(16 if phase=='pilot' else 160)
 return rows,slowest

def summaries(rows):
 result=[]
 for source in dict.fromkeys(r['source'] for r in rows):
  for cat in ['all']+P['categories']:
   parents=[r for r in rows if r['source']==source and (cat=='all' or r['category']==cat)]
   for label in CLASSES:
    values=[r['classes'][label] for r in parents];n=sum(r['N'] for r in values);ss=math.fsum(r['pull2'] for r in values)
    result.append(dict(source=source,fit_support_category=cat,deposit_class=label,parents_N=len(parents),
     matched_supported_parents_N=sum(r['matched'] and r['start_supported'] for r in parents),candidates_N=n,pull2_sum=ss,
     pull_RMS=math.sqrt(ss/n) if n else None,abs_pull_gt3_N=sum(r['abs_pull_gt3_N'] for r in values),
     residual2_sum_mm2=math.fsum(r['residual2_mm2'] for r in values)))
 for row in result:
  total=next(q['pull2_sum'] for q in result if q['source']==row['source'] and q['deposit_class']==row['deposit_class'] and q['fit_support_category']=='all')
  row['fraction_of_class_pull2_sum']=row['pull2_sum']/total if total else None
 return result
