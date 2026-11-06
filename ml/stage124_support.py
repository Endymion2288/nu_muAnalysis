"""Batch-only effective-support ledger and bounded exact EVNT schema/cost probe."""
import csv,json,time,resource
from pathlib import Path
import numpy as np
import uproot
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage124_energy_ml'
def main():
 tick=time.perf_counter();cpu=time.process_time()
 with np.load(ROOT/'ntuples/energy_ml_stage124/input.npz') as z:d={k:z[k] for k in z.files}
 with np.load(ROOT/'ntuples/energy_ml_stage119/curve_input.npz') as z:new={k:z[k] for k in z.files}
 rows=[]
 for pool,a in [('old',d),('Stage119_expansion',new)]:
  energy=a['truth_E_GeV'];pz=a.get('pz',a.get('reco_pz_GeV'));incoming=a['incoming'];role=a['role'];eligible=np.ones(len(role),bool) if pool=='old' else a['kind']=='expansion'
  for rr in [0,1,2,3]:
   ix=np.flatnonzero(eligible&(role==rr));_,gid,count=np.unique(incoming[ix],axis=0,return_inverse=True,return_counts=True);w=1/count[gid]
   for layer,m in [('E50_100',(energy>=50)&(energy<100)),('E100_200',(energy>=100)&(energy<200)),('pz50_100_trueE200',(pz>=50)&(pz<100)&(energy>=200)),('high_y',a['y_lepton']>=.8),('all',np.ones(len(energy),bool))]:
    use=m[ix];ww=w[use];rows.append(dict(pool=pool,role=rr,stratum=layer,rows=int(use.sum()),incoming_proxies=len(np.unique(incoming[ix[use]],axis=0)),ESS_records=float(ww.sum()**2/(ww@ww)) if len(ww) else 0,certified_new_GENIE_families='not_certified',prediction_budget=0 if pool!='old' or rr==0 else 'original_developed_roles_only'))
 with (OUT/'sample_scale.tsv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
 audit=json.loads((ROOT/'workbook/stage120_energy_ml/provenance_audit.json').read_text());paths=[]
 def visit(x):
  if isinstance(x,dict):
   for k,v in x.items():
    if k=='input_file' and isinstance(v,str) and v.endswith('EVNT.pool.root'):paths.append(v)
    else:visit(v)
  elif isinstance(x,list):
   for v in x:visit(v)
 visit(audit);paths=list(dict.fromkeys(paths));metadata=[]
 for path in paths:
  start=time.perf_counter();record=dict(path=path,exists=Path(path).is_file())
  if record['exists']:
   with uproot.open(path,array_cache=None) as f:
    trees={}
    for name in f.keys(cycle=False):
     obj=f[name]
     if hasattr(obj,'num_entries'):trees[name]=dict(entries=obj.num_entries,branches=obj.typenames())
    record.update(trees=trees,read_bytes=int(f.file.source.num_requested_bytes),file_bytes=Path(path).stat().st_size)
  record['wall_s']=time.perf_counter()-start;metadata.append(record)
  print('EVNT_SCHEMA',path,record.get('read_bytes',0),flush=True)
 report=dict(inputs=metadata,scope='exact Stage120 retained generator paths only; no directory scan, no event content read or parent association inferred',old_N0_definition='old train two-low/hard incoming proxies and ESS; not certified independent GENIE families',feasible_native_X_XZ='existing same-support old pool, original full scale; no independent N added',independent_2N_gate='not_met: known old producers and historical exposure incomplete; Stage119 new train low52 is far below a940 increment. Native relation experiment proceeds independently.',expansion_decision='no small9–36 rerun and no unverified sample count increase; exact EVNT metadata alone cannot certify original complete histories or predict selected yield/cost of new full G4',requirements_for_new_parent_purchase=['exact EVNT entry/full final state and parent identity from start','explicit old exposure intersection and independently locked confirmation families','record truth-directed sampling probability including hard/transition/natural controls','measure full G4/reco cost on actual new step before freezing old-scale ~2N; current cost unmeasured'],CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,new_fit=0,new_forward=0,new_generation=0)
 (OUT/'sample_strategy.json').write_text(json.dumps(report,indent=2)+'\n');print('SUPPORT_COMPLETE',report['CPU_s'],flush=True)
if __name__=='__main__':main()
