"""Complete only the unused B fit after A serialization failure; never refit A."""
import csv,json,time,resource
from pathlib import Path
import numpy as np
import xgboost as xgb
from audited_features import build
from stage99_activity import FEATURES
from stage99_report import save,table,boot,ci,curve
R=Path(__file__).resolve().parents[1];O=R/'workbook/stage99_energy_ml'
def load(p):
 with np.load(R/p) as z:return {k:z[k] for k in z.files}
def rows(p):
 path=R/'ntuples/energy_ml_stage99'/p if p in ['B_collection_features.tsv','B_identities.tsv'] else O/p
 return list(csv.DictReader(path.open(),delimiter='\t'))
def main():
 assert not (O/'B_complete.json').exists(), 'The two classifier fits are already used'
 (R/'ml/artifacts/stage99').mkdir(parents=True,exist_ok=True)
 t=time.perf_counter();cpu=time.process_time();failure=json.loads((O/'B_failure.json').read_text());assert failure['completed_classifier_fits']==1 and failure['remaining_allowed_classifier_fits']==1
 co=json.loads((R/'ntuples/energy_ml_stage95/cohort.json').read_text());cases=co['records'];feature={int(v['row']):v for v in rows('B_collection_features.tsv')};meta={int(v['row']):v for v in rows('B_identities.tsv')};x=np.array([[float(feature[c['row']][k]) for k in FEATURES] for c in cases]);old=load('ntuples/energy_ml_stage55/dataset.npz');read=load('ntuples/energy_ml_stage56/readout.npz');baseline=np.full((len(cases),62),np.nan)
 for origin in sorted({c['origin'] for c in cases}):
  ids=np.array([i for i,c in enumerate(cases) if c['origin']==origin]);orow=np.array([cases[i]['origin_row'] for i in ids])
  if origin==55:
   ix=np.searchsorted(read['row'],orow);assert np.array_equal(read['row'][ix],orow);small={k:v[ix] for k,v in read.items() if k!='metadata_json'};baseline[ids]=build(old,small)
  else:baseline[ids]=load(f'ntuples/energy_ml_stage{origin}/support.npz')['x'][orow]
 avail=np.array([int(meta[c['row']]['available']) for c in cases]);flags=np.array([c['status_other'] for c in cases]);A=np.column_stack([baseline,np.isnan(baseline),flags,avail,np.zeros(len(cases))]);B=np.column_stack([A,x,np.isnan(x)])
 E=np.array([c['reference_truth_E_GeV'] for c in cases]);pz=np.array([c['pz_GeV'] for c in cases]);role=np.array([c['role'] for c in cases]);labels=(E>=200).astype(int);domain=(pz>50)&(pz<100)&(((E>=50)&(E<100))|(E>=200));tr=domain&(role==1);cal=domain&(role==2)
 model=xgb.XGBClassifier(n_estimators=100,max_depth=2,learning_rate=.05,min_child_weight=10,reg_lambda=10,random_state=2026110499,n_jobs=1,tree_method='hist',objective='binary:logistic',eval_metric='logloss');model.fit(B[tr],labels[tr]);q=np.clip(model.predict_proba(B[cal])[:,1].astype(float),1e-12,1-1e-12);trainq=model.predict_proba(B[tr])[:,1].astype(float);pids=np.flatnonzero(cal);y=labels[cal]
 # Persist recoverable numerical results before optional serialization/report work.
 table('B_classifier_predictions.tsv',[dict(row=cases[i]['row'],label=int(labels[i]),B=float(v)) for i,v in zip(pids,q)])
 model.get_booster().save_model(R/'ml/artifacts/stage99/B_classifier_B.json')
 sub=dict(key_id=np.array([cases[i]['key_id'] for i in pids]),component=np.array([cases[i]['component'] for i in pids]));gid,draw=boot(sub,2026110499);bw=draw[:,gid];den=bw.sum(1);ll=-(y*np.log(q)+(1-y)*np.log1p(-q));br=(q-y)**2;lci=ci(bw@ll/den);bci=ci(bw@br/den);fp,tp,auc,pauc=curve(q,y,np.ones(len(y)))
 table('B_classifier_metrics.tsv',[dict(model='B',N=len(y),L_N=int((y==0).sum()),H_N=int((y==1).sum()),logscore=float(ll.mean()),logscore_low95=lci[0],logscore_high95=lci[1],Brier=float(br.mean()),Brier_low95=bci[0],Brier_high95=bci[1],AUC=auc,pAUC_0_10=pauc,A_comparison='unmeasured: completed A predictions lost on serialization failure')])
 work=[];trainL=trainq[labels[tr]==0];v=np.unique(trainL);fpr=np.array([np.mean(trainL>threshold) for threshold in v])
 for alpha in [.02,.05,.1]:
  threshold=float(v[np.flatnonzero(fpr<=alpha+1e-14)[0]]);flag=q>threshold;row=dict(model='B',nominal_FPR=alpha,train_threshold=threshold,train_FPR=float(np.mean(trainL>threshold)),certified=False)
  for cls,lab in [(0,'L_FPR'),(1,'H_TPR')]:
   z=y==cls;bc=bw[:,z];de=bc.sum(1);bs=np.divide(bc@flag[z].astype(float),de,out=np.full(len(de),np.nan),where=de>0);bounds=ci(bs);row.update({lab:float(flag[z].mean()),lab+'_low95':bounds[0],lab+'_high95':bounds[1],lab+'_N':int(z.sum()),lab+'_recognized':int(flag[z].sum())})
  work.append(row)
 table('B_classifier_ROC_working.tsv',work)
 costs=rows('B_sources.tsv');tt=(O/'time_breport.txt').read_text();statuses={s:sum(m['status']==s for m in meta.values()) for s in sorted({m['status'] for m in meta.values()})};strata=[]
 for field in ['source','component','role','status_other']:
  for val in sorted({str(c[field]) for c in cases}):
   ids=[i for i,c in enumerate(cases) if str(c[field])==val];strata.append(dict(grouping=field,group=val,N=len(ids),collection_readable=int(avail[ids].sum()),source_unavailable=sum(meta[cases[i]['row']]['status']=='source_unavailable' for i in ids),join_failed=sum(meta[cases[i]['row']]['status']=='identity_join_failed' for i in ids),empty_collections=sum(meta[cases[i]['row']].get('empty_collection')=='True' for i in ids),single_track=sum(meta[cases[i]['row']].get('n_tracks')=='1' for i in ids),native_exact_available=0))
 for name,ids in [('pz50_100',[i for i,c in enumerate(cases) if c['pz_GeV']<100]),('pz100plus',[i for i,c in enumerate(cases) if c['pz_GeV']>=100])]:strata.append(dict(grouping='X_pz',group=name,N=len(ids),collection_readable=int(avail[ids].sum()),native_exact_available=0))
 table('B_availability_strata.tsv',strata)
 summary=[]
 for j,name in enumerate(FEATURES):
  a=x[:,j];z=np.isfinite(a);summary.append(dict(feature=name,unit='mm' if name.endswith('_mm') else 'plane_index' if name=='first_outside10_plane' else 'entries',finite_N=int(z.sum()),missing_N=int((~z).sum()),mean=float(a[z].mean()) if z.any() else None,median=float(np.median(a[z])) if z.any() else None,p95=float(np.quantile(a[z],.95)) if z.any() else None))
 table('B_activity_summary.tsv',summary)
 save('B_complete.json',dict(collection_measurement_complete=True,paired_information_comparison_complete=False,N=len(cases),unique_incoming=len({c['key_id'] for c in cases}),collection_readable=int(avail.sum()),statuses=statuses,native_exact_available=0,real_ID_association_available=0,classifier_fit_count_total=2,completed_fits=['A (output lost during serialization)','B (retained)'],retained_classifier_cells=['B'],A_refits=0,source_reextraction=0,new_energy_fits=0,requested_bytes=sum(int(c['requested_bytes']) for c in costs),native_event_payload_bytes=0,physical_network_bytes='unmeasured',minimum_missing_pilot_product='A predictions from one separately authorized fixed fit, matched to retained B; no further ROOT extraction required',finish_CPU_s=time.process_time()-cpu,finish_wall_s=time.perf_counter()-t,peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024))
if __name__=='__main__':main()
