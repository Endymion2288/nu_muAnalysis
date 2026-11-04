"""Stage99 bounded collection fallback and preregistered two-classifier information pilot."""
import csv,json,time,resource,sys,multiprocessing as mp
from pathlib import Path
import numpy as np
import uproot,awkward as ak
R=Path(__file__).resolve().parents[1];O=R/'workbook/stage99_energy_ml'
from stage99_report import table,save,boot,ci,curve
CFG=json.loads((O/'activity_contract.json').read_text())
EV={int(x['row']):x for x in csv.DictReader((R/'ntuples/energy_ml_stage95/events.tsv').open(),delimiter='\t')}
CANDS={}
for x in csv.DictReader((R/'ntuples/energy_ml_stage95/candidates.tsv').open(),delimiter='\t'):
 if x['leading']=='True':CANDS[int(x['row'])]=x
FEATURES=[f's{s}_entries' for s in range(4)]+[f's{s}l{l}_{q}' for s in [1,2,3] for l in range(3) for q in ['entries','outside10','outside50','rms_radius_mm']]+['outside10_growth_s3_minus_s1','first_outside10_plane']
COLS=['run','eventID','SpacePoints','SpacePoint_x','SpacePoint_y','SpacePoint_z','Track_pz0']+[f'nClusters{s}' for s in range(4)]
def summarize(xyz,c):
 v=np.full(len(FEATURES),np.nan);cent=np.array(CFG['centers_mm']);off=np.array(CFG['layer_offsets_mm']);finite=np.isfinite(xyz).all(1);xyz=xyz[finite];z=xyz[:,2];st=abs(z[:,None]-cent).argmin(1) if len(z) else np.array([],int);la=abs(z[:,None]-cent[st,None]-off).argmin(1) if len(z) else np.array([],int);supported=(abs(z-cent[st]-off[la])<=10)
 for s in range(4):v[s]=np.sum(supported&(st==s))
 raw=np.array([float(c[k]) for k in ['x0_mm','y0_mm','z0_mm','x1_mm','y1_mm','z1_mm']]);good=np.isfinite(raw).all() and not np.isin(raw,[999999,-999]).any() and raw[5]>raw[2]
 radius=np.full(len(z),np.nan)
 if good:
  x,y,z0,x1,y1,z1=raw;f=(z-z0)/(z1-z0);dx=xyz[:,0]-x-f*(x1-x);dy=xyz[:,1]-y-f*(y1-y);take=(z>=z0-10)&(z<=z1+10);radius[take]=np.hypot(dx[take],dy[take])
 sums=[];active=[];j=4
 for s in [1,2,3]:
  count=0
  for l in range(3):
   a=supported&(st==s)&(la==l);v[j]=a.sum();rr=radius[a];valid=np.isfinite(rr);reference_valid=good and cent[s]+off[l]>=raw[2]-10 and cent[s]+off[l]<=raw[5]+10
   if reference_valid:
    v[j+1]=np.sum(rr[valid]>10);v[j+2]=np.sum(rr[valid]>50);v[j+3]=np.sqrt(np.mean(rr[valid]**2)) if valid.any() else np.nan;count+=v[j+1]
    if v[j+1]>0:active.append((s-1)*3+l)
   j+=4
  sums.append(count)
 if good:v[-2]=sums[2]-sums[0];v[-1]=min(active) if active else np.nan
 return v,dict(nonfinite_points=int((~finite).sum()),unsupported_z_points=int((~supported).sum()),chord_valid=bool(good),coordinate_duplicate_entries=int(len(xyz)-len(np.unique(xyz,axis=0))),empty_collection=len(xyz)==0)
def one_source(task):
 source,cases=task;tick=time.perf_counter();cpu=time.process_time();rows=[];cost=dict(source=source['source'],N=len(cases),requested_bytes=0,native_event_payload_bytes=0)
 if not source['input'] or not Path(source['input']).is_file():
  for c in cases:rows.append((c['row'],np.full(len(FEATURES),np.nan),dict(row=c['row'],source=source['source'],status='source_unavailable',available=0)))
 else:
  with uproot.open(source['input'],array_cache='64 MB') as f:
   t=f['nt'];missing=[k for k in COLS if k not in t];assert not missing,missing
   # Read contiguous baskets once per source span; only summarize requested identities.
   entries=[int(EV[c['row']]['input_entry']) for c in cases];lo=min(entries);hi=max(entries)+1
   a=t.arrays(COLS,entry_start=lo,entry_stop=hi)
   for c,entry in zip(cases,entries):
    j=entry-lo;e=EV[c['row']];meta=dict(row=c['row'],source=source['source'],status='ok',available=1)
    if int(a['run'][j])!=c['run'] or int(a['eventID'][j])!=c['eventID']:
     meta.update(status='identity_join_failed',available=0);rows.append((c['row'],np.full(len(FEATURES),np.nan),meta));continue
    arr=ak.to_numpy(a['Track_pz0'][j])/1000;lead=int(e['lead_index']);assert lead==int(np.nanargmax(arr)) and abs(arr[lead]-c['pz_GeV'])<1e-8
    assert len(arr)==int(e['n_tracks'])
    xyz=np.column_stack([ak.to_numpy(a[k][j]) for k in ['SpacePoint_x','SpacePoint_y','SpacePoint_z']]);assert len(xyz)==int(a['SpacePoints'][j]);v,check=summarize(xyz,CANDS[c['row']]);meta.update(check,SP_entries=len(xyz),input_entry=entry,n_tracks=len(arr),associated_unique_SP='unmeasured',associated_unique_clusters='unmeasured',active_readout_denominator='unmeasured',actual_covariance='unmeasured')
    for s in range(4):meta[f'nClusters{s}']=int(a[f'nClusters{s}'][j])
    rows.append((c['row'],v,meta))
   cost['requested_bytes']=int(f.file.source.num_requested_bytes)
 cost.update(CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick)
 return rows,cost

def main(qa=False):
 if not qa:
  assert not (O/'B_failure.json').exists() and not (O/'B_complete.json').exists(), 'Do not repeat completed classifier fits'
  (R/'ml/artifacts/stage99').mkdir(parents=True,exist_ok=True)
 tick=time.perf_counter();cpu=time.process_time();co=json.loads((R/'ntuples/energy_ml_stage95/cohort.json').read_text());cases=[x for x in co['records'] if x['qa']][:40] if qa else co['records'];assert len({x['key_id'] for x in cases})==len(cases);assert all(x['role'] in [1,2] for x in cases)
 tasks=[(s,[c for c in cases if c['source']==s['source']]) for s in co['sources']];tasks=[t for t in tasks if t[1]]
 with mp.get_context('fork').Pool(8) as p:ret=p.map(one_source,tasks)
 rr={r[0]:r for rows,_ in ret for r in rows};x=np.stack([rr[c['row']][1] for c in cases]);meta=[rr[c['row']][2] for c in cases];cost=[z[1] for z in ret];prefix='B_QA' if qa else 'B';table(prefix+'_identities.tsv',meta);table(prefix+'_sources.tsv',cost)
 if qa:
  passed=sum(z['available'] for z in meta);assert passed>0
  save('B_QA.json',dict(passed=True,identities=len(cases),collection_readable=passed,sources=len(tasks),CPU_source_sum_s=sum(z['CPU_s'] for z in cost),requested_bytes=sum(z['requested_bytes'] for z in cost),wall_s=time.perf_counter()-tick,new_fits=0,features=FEATURES,original_leading_index_pz_checked=True,SP_scalar_vector_counts_checked=True,measured_covariance=False,real_ID_association=False))
  return
 assert json.loads((O/'B_QA.json').read_text())['passed'];assert sum(z['requested_bytes'] for z in cost)<1e10
 table('B_collection_features.tsv',[dict(row=c['row'],**dict(zip(FEATURES,v))) for c,v in zip(cases,x)])
 # Build the original audited 62 values without new energy model inference.
 from audited_features import build
 def load(p):
  with np.load(R/p) as z:return {k:z[k] for k in z.files}
 old=load('ntuples/energy_ml_stage55/dataset.npz');read=load('ntuples/energy_ml_stage56/readout.npz');baseline=np.full((len(cases),62),np.nan)
 for origin in sorted({c['origin'] for c in cases}):
  ids=np.array([i for i,c in enumerate(cases) if c['origin']==origin]);orow=np.array([cases[i]['origin_row'] for i in ids])
  if origin==55:
   ix=np.searchsorted(read['row'],orow);assert np.array_equal(read['row'][ix],orow);small={k:v[ix] for k,v in read.items() if k!='metadata_json'};baseline[ids]=build(old,small)
  else:baseline[ids]=load(f'ntuples/energy_ml_stage{origin}/support.npz')['x'][orow]
 avail=np.array([z['available'] for z in meta]);exact_native=np.zeros(len(cases));flags=np.array([c['status_other'] for c in cases]);A=np.column_stack([baseline,np.isnan(baseline),flags,avail,exact_native]);B=np.column_stack([A,x,np.isnan(x)])
 # Labels only enter here, after frozen payload and classifier definition.
 E=np.array([c['reference_truth_E_GeV'] for c in cases]);pz=np.array([c['pz_GeV'] for c in cases]);roles=np.array([c['role'] for c in cases]);target=(E>=200).astype(int);LH=((E>=50)&(E<100))|(E>=200);domain=(pz>50)&(pz<100)&LH
 support=[]
 for role in [1,2]:
  for cls in [0,1]:
   z=domain&(roles==role)&(target==cls);support.append(dict(role=role,label=cls,N=int(z.sum()),collection_readable=int(avail[z].sum()),sources=len({c['source'] for c,a in zip(cases,z) if a})))
 table('B_class_support.tsv',support);eligible=all(z['N']>=20 for z in support);results=[];working=[];newfits=0
 if eligible:
  import xgboost as xgb
  tr=domain&(roles==1);cal=domain&(roles==2);pred=[];train_predictions=[]
  for name,xx in [('A',A),('B',B)]:
   model=xgb.XGBClassifier(n_estimators=100,max_depth=2,learning_rate=.05,min_child_weight=10,reg_lambda=10,random_state=2026110499,n_jobs=1,tree_method='hist',objective='binary:logistic',eval_metric='logloss');model.fit(xx[tr],target[tr]);newfits+=1;q=model.predict_proba(xx[cal])[:,1].astype(float);pred.append(q);train_predictions.append(model.predict_proba(xx[tr])[:,1].astype(float));model.get_booster().save_model(R/f'ml/artifacts/stage99/B_classifier_{name}.json')
  labels=target[cal];pids=np.flatnonzero(cal);sub=dict(key_id=np.array([cases[i]['key_id'] for i in pids]),component=np.array([cases[i]['component'] for i in pids]));gid,draw=boot(sub,2026110499);bw=draw[:,gid];den=bw.sum(1);losses=[]
  for name,q,trainq in zip(['A','B'],pred,train_predictions):
   q=np.clip(q,1e-12,1-1e-12);logloss=-(labels*np.log(q)+(1-labels)*np.log1p(-q));brier=(q-labels)**2;losses.append((logloss,brier));bounds1=ci((bw@logloss)/den);bounds2=ci((bw@brier)/den);fp,tp,auc,pauc=curve(q,labels,np.ones(len(q)));results.append(dict(model=name,N=len(q),L_N=int((labels==0).sum()),H_N=int((labels==1).sum()),logscore=float(logloss.mean()),logscore_low95=bounds1[0],logscore_high95=bounds1[1],Brier=float(brier.mean()),Brier_low95=bounds2[0],Brier_high95=bounds2[1],AUC=auc,pAUC_0_10=pauc))
   # Freeze train-only empirical low-FPR thresholds; no cal target selection.
   trainL=trainq[target[tr]==0];v=np.unique(trainL)
   for alpha in [.02,.05,.1]:
    empirical=np.array([np.mean(trainL>t) for t in v]);threshold=float(v[np.flatnonzero(empirical<=alpha+1e-14)[0]]);flag=q>threshold
    row=dict(model=name,nominal_FPR=alpha,train_threshold=threshold,train_FPR=float(np.mean(trainL>threshold)),certified=False,meaning='train-frozen threshold, original quota-cohort cal evaluation; no population guarantee')
    for cls,lab in [(0,'L_FPR'),(1,'H_TPR')]:
     z=labels==cls;bc=bw[:,z];dd=bc.sum(1);bs=np.divide(bc@flag[z].astype(float),dd,out=np.full(len(dd),np.nan),where=dd>0);bounds=ci(bs);row.update({lab:float(flag[z].mean()),lab+'_low95':bounds[0],lab+'_high95':bounds[1],lab+'_N':int(z.sum()),lab+'_recognized':int(flag[z].sum())})
    working.append(row)
  delta=[]
  for j,name in enumerate(['logscore','Brier']):
   v=losses[1][j]-losses[0][j];bounds=ci((bw@v)/den);delta.append(dict(metric=name,B_minus_A=float(v.mean()),low95=bounds[0],high95=bounds[1]))
  table('B_classifier_metrics.tsv',results);table('B_classifier_delta.tsv',delta);table('B_classifier_ROC_working.tsv',working)
  table('B_classifier_predictions.tsv',[dict(row=cases[i]['row'],label=int(target[i]),A=float(a),B=float(b)) for i,a,b in zip(pids,*pred)])
 child=resource.getrusage(resource.RUSAGE_CHILDREN);save('B_complete.json',dict(passed=True,N=len(cases),collection_readable=int(avail.sum()),collection_unavailable=int((avail==0).sum()),native_exact_available=0,association_ID_available=0,new_classifier_fits=newfits,eligible=eligible,CPU_self_s=time.process_time()-cpu,CPU_child_s=child.ru_utime+child.ru_stime,CPU_source_sum_s=sum(z['CPU_s'] for z in cost),wall_s=time.perf_counter()-tick,peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,requested_bytes=sum(z['requested_bytes'] for z in cost),native_event_payload_bytes=0,physical_network_bytes='unmeasured',collection_scope='PHYS entries and geometric endpoint chord; no native association or actual covariance',new_energy_fits=0))
if __name__=='__main__':main('--qa' in sys.argv)
