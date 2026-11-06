"""Fixed original-scale native association X/X+Z energy and tail experiment."""
import csv,gzip,json,multiprocessing as mp,resource,time
from pathlib import Path
import numpy as np
import xgboost as xgb
from audited_features import configuration
from stage119_curve_common import masks,weights,LAYERS
from stage119_reportcurve import metrics,ci
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage124_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage124';ART=ROOT/'ml/artifacts/stage124'
def table(name,rows):
 if not rows:return
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with (OUT/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=keys,delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
def load(path):
 with np.load(path) as z:return {k:z[k] for k in z.files if k!='metadata_json'}
def prepare():
 d=load(CACHE/'input.npz');contract=json.loads((OUT/'native_contract.json').read_text());fc=json.loads((OUT/'feature_contract.json').read_text())
 with gzip.open(CACHE/'mismatch_125/native.json.gz','rt') as f:diag=json.load(f)
 v=diag['records'][0];a=v['phys_audit'];ii=int(np.argmax(a['Track_pz0']));tt=max(v['track_audit'],key=lambda t:t[0])
 diagnostic=dict(row=v['row'],run=v['run'],event=v['event'],cached_pz_GeV=float(d['pz'][v['row']]),current_PHYS_pz_GeV=a['Track_pz0'][ii]/1000,REC_pz_GeV=v['pz_GeV'],PHYS_track_N=len(a['Track_pz0']),REC_long_track_N=v['longTracks'],current_PHYS_minus_REC_position_mm={axis:a['Track_'+axis+'0'][ii]-tt[j+2] for j,axis in enumerate(['x','y','z'])},PHYS=a,REC_merged_track_audit_columns=['pz_MeV','qOverP_MeVinv','x_mm','y_mm','z_mm','chi2','nDoF','measurement_N'],REC_merged_track_audit=v['track_audit'],scope='exact same event directed interface audit; incomplete original measurement IDs/producer history, do not certify same leading track or diagnose cause from pz alone',handling='all parent/X retained; unknown leading-specific Z fieldsNaN; no relaxed matching tolerance')
 (OUT/'native_mismatch_audit.json').write_text(json.dumps(diagnostic,indent=2)+'\n')
 z=np.full((len(d['role']),104),np.nan);available=np.zeros(len(z),bool);loaded=np.zeros(len(z),bool);records=[];cost=[]
 for i,batch in enumerate(contract['batches']):
  path=CACHE/f'repair_{i}/native.json.gz'
  if not path.exists():path=CACHE/f'native_{i}/native.json.gz'
  with gzip.open(path,'rt') as f:r=json.load(f)
  assert len(r['records'])==sum(len(contract['requests'][j]['cases']) for j in batch)
  cost.append({k:v for k,v in r.items() if k not in ['records','metadata']})
  for v in r['records']:
   j=v['row'];assert not loaded[j];assert v['run']==d['run'][j] and v['event']==d['eventID'][j]
   matched=np.isclose(v['pz_GeV'],d['pz'][j],rtol=3e-7,atol=3e-5);assert v.get('pz_match',True)==matched
   if not matched:assert all(np.isnan(v['z'][k]) for k in [24*st+k for st in range(4) for k in [17,18]]+[98,103])
   assert len(v['z'])==104;z[j]=v['z'];loaded[j]=True;records.append(v)
   names=configuration()['features']
   closed=v['clusters']==[int(d['x'][j,names.index('nClusters'+str(s))]) for s in range(4)] and v['sp']==int(d['x'][j,names.index('SpacePoints')]) and v['longTracks']==int(d['x'][j,names.index('longTracks')])
   v['count_closed']=closed;available[j]=closed
   if not closed:z[j]=np.nan
 assert loaded.all();assert all(v['invalidRaw']==0 for v in records)
 table('native_identity_exceptions.tsv',[dict(row=v['row'],run=v['run'],event=v['event'],source_index=v['source_index'],entry=v['entry'],pz_match=v.get('pz_match',True),PHYS_pz_GeV=d['pz'][v['row']],REC_pz_GeV=v['pz_GeV'],count_closed=v['count_closed'],policy='parent/X/role retained; unmatched leading fields NaN; count mismatch allZunknown') for v in records if not v.get('pz_match',True) or not v['count_closed']])
 features=np.column_stack([z[:,f['native_index']]*f.get('scale',1) for f in fc['Z']]+[available.astype(float)]).astype('float32')
 assert features.shape[1]==57;d['XZ']=np.column_stack([d['x'],features]);d['z_available']=available;d['native_leading_unknown']=np.zeros(len(available),bool)
 for v in records:d['native_leading_unknown'][v['row']]=not v.get('pz_match',True)
 np.savez_compressed(CACHE/'comparison_input.npz',**d);table('native_cost.tsv',cost)
 coverage=[]
 for role in [0,1,2,3]:
  for layer,m in masks(d).items():
   ix=np.flatnonzero((d['role']==role)&m)
   lookup={r['row']:r for r in records};rr=[lookup[int(j)] for j in ix]
   coverage.append(dict(role=role,stratum=layer,N=len(ix),native_available_N=int(available[ix].sum()),leading_identity_unknown_N=sum(not r.get('pz_match',True) for r in rr),count_mismatch_N=sum(not r['count_closed'] for r in rr),SP_links=sum(r['spLinks'] for r in rr),SP_missing=sum(r['spMissing'] for r in rr),track_measurements=sum(r['measurements'] for r in rr),track_missing=sum(r['measurementMissing'] for r in rr),raw_missing=sum(r['rawMissing'] for r in rr),invalid_cluster_IDs=sum(r['invalidCluster'] for r in rr),invalid_cluster_ID_events=sum(r['invalidCluster']>0 for r in rr),duplicate_cluster_identifier_events=sum(r['duplicateClusterIdentifiers']>0 for r in rr)))
 table('native_coverage.tsv',coverage)
 dynamic=[]
 for f,v in zip(fc['Z'],features.T):
  m=(d['role']>0)&np.isfinite(v);dynamic.append(dict(name=f['name'],N=int(m.sum()),minimum=float(v[m].min()) if m.any() else None,maximum=float(v[m].max()) if m.any() else None,sd=float(v[m].std()) if m.any() else None,zero_N=int((v[m]==0).sum())))
 table('feature_dynamic_range.tsv',dynamic)
 return d

def fit(spec):
 arm,d=spec;cpu=time.process_time();tick=time.perf_counter();x=d['x'] if arm=='X' else d['XZ'];train=d['role']==1;cal=d['role']==2;active=d['role']>0;y=np.log(d['truth_E_GeV']);w=weights(d['incoming'][train]);names=configuration()['features']+([] if arm=='X' else [f['name'] for f in json.loads((OUT/'feature_contract.json').read_text())['Z']]+['native_available'])
 dm=xgb.DMatrix(x[train],label=y[train],weight=w,feature_names=names,nthread=1);evaluation=xgb.DMatrix(x[active],feature_names=names,nthread=1);p=json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())['baseline'];pred=[]
 for seed in p['seeds']:
  params=dict(p['xgboost'],seed=seed,base_score=float(np.average(y[train],weights=w)),boost_from_average=0);model=xgb.train(params,dm,num_boost_round=p['rounds']);path=ART/f'{arm}_{seed}.ubj';model.save_model(path)
  again=xgb.Booster(params={'nthread':1});again.load_model(path);a=model.predict(evaluation).astype(float);np.testing.assert_array_equal(a,again.predict(evaluation));pred.append(a)
 raw=np.full(len(y),np.nan);raw[active]=np.mean(pred,axis=0);offset=float(np.average(y[cal]-raw[cal],weights=weights(d['incoming'][cal])));np.savez_compressed(ART/f'{arm}_prediction.npz',raw=raw,cal=raw+offset)
 return dict(arm=arm,features=x.shape[1],train_N=int(train.sum()),train_incoming=len(np.unique(d['incoming'][train],axis=0)),cal_N=int(cal.sum()),offset=offset,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,reload_exact=True)

def evaluate(d):
    policies={arm:load(ART/f'{arm}_prediction.npz')['cal'] for arm in ['X','XZ']}
    cached=load(ROOT/'ml/artifacts/stage87/predictions.npz');active=np.flatnonzero(d['role']>0)
    np.testing.assert_array_equal(cached['row'],active)
    policies['direct_cal']=np.full(len(d['role']),np.nan)
    policies['direct_cal'][active]=cached['direct_cal']
    policies['traditional']=np.log(d['pz']/.8)
    for v in policies.values():v[d['role']==0]=np.nan
    points=[];pairs=[];support=[];power=[];validations=[];gates=[]
    for role in [1,2,3]:
        selected=np.flatnonzero(d['role']==role);sd={k:v[selected] for k,v in d.items()};_,first,gid=np.unique(sd['incoming'],axis=0,return_index=True,return_inverse=True)
        nk=len(first);rng=np.random.default_rng(20261106124+role);draw=np.zeros((500,nk),np.int16)
        for component in sorted(set(sd['component'][first])):
            use=np.flatnonzero(sd['component'][first]==component);draw[:,use]=rng.multinomial(len(use),np.full(len(use),1/len(use)),size=500)
        w=weights(sd['incoming']);np.testing.assert_allclose(w,sd['weight'],rtol=0,atol=1e-12);names=list(policies)
        for layer,mask in masks(sd).items():
            use=selected[mask];ww=w[mask];gg=gid[mask]
            if not len(use):
                support.append(dict(role=role,stratum=layer,N=0,incoming=0));continue
            err=np.column_stack([policies[n][use]-np.log(d['truth_E_GeV'][use]) for n in names]);assert np.isfinite(err).all()
            den=draw@np.bincount(gg,weights=ww,minlength=nk);good=den>0
            agg=np.zeros((nk,len(names)));np.add.at(agg,gg,ww[:,None]*err**2);bt=draw@agg
            base=dict(role=role,stratum=layer,N=len(use),incoming=len(np.unique(gg)),ESS=float(ww.sum()**2/(ww@ww)),valid_draws=int(good.sum()))
            support.append(base)
            for j,name in enumerate(names):
                lo,hi=ci(np.sqrt(bt[good,j]/den[good]));points.append(dict(**base,model=name,**metrics(err[:,j],ww),RMSE_low95=lo,RMSE_high95=hi))
            rel=np.expm1(err);tails={}
            for sign,flag in [('total',abs(rel)>.5),('positive',rel>.5),('negative',rel<-.5)]:
                a=np.zeros_like(agg);np.add.at(a,gg,ww[:,None]*flag);tails[sign]=(a.sum(0)/ww.sum(),draw@a)
            for candidate,ref in [('XZ','X')]+[(a,b) for a in ['X','XZ'] for b in ['direct_cal','traditional']]:
                j,k=names.index(candidate),names.index(ref);ok=good&(bt[:,k]>0);lo,hi=ci(np.sqrt(bt[ok,j]/bt[ok,k]))
                mse_delta=(agg[:,j].sum()-agg[:,k].sum())/ww.sum();dl,dh=ci((bt[ok,j]-bt[ok,k])/den[ok])
                row=dict(**base,candidate=candidate,reference=ref,RMSE_ratio=float(np.sqrt(agg[:,j].sum()/agg[:,k].sum())),low95=lo,high95=hi,MSE_delta=float(mse_delta),MSE_delta_low95=dl,MSE_delta_high95=dh)
                for sign,(central,t) in tails.items():
                    lo,hi=ci(100*(t[ok,j]-t[ok,k])/den[ok]);row.update({sign+'_tail_delta_pp':float(100*(central[j]-central[k])),sign+'_tail_low95_pp':lo,sign+'_tail_high95_pp':hi})
                pairs.append(row)
                if candidate=='XZ' and ref=='X' and layer in LAYERS and row['low95'] is not None:
                    rw=draw[:,gg]*ww;ind=ci(np.sqrt((rw@err[:,j]**2)/(rw@err[:,k]**2)))
                    delta=max(abs(ind[0]-row['low95']),abs(ind[1]-row['high95']));assert delta<1e-10
                    validations.append(dict(role=role,stratum=layer,paired_interval_max_abs=delta))
                if candidate=='XZ' and ref=='X' and role==2:
                    contrast=err[:,j]**2-.95**2*err[:,k]**2
                    counts=np.bincount(gg,weights=ww,minlength=nk);has=counts>0
                    values=np.bincount(gg,weights=ww*contrast,minlength=nk)[has]/counts[has]
                    delta=.0975*float(np.average(err[:,k]**2,weights=ww));variance=float(np.var(values,ddof=1)) if len(values)>1 else np.nan
                    needed=int(np.ceil((1.95996398454+.84162123357)**2*variance/delta**2)) if np.isfinite(variance) and delta>0 else None
                    power.append(dict(candidate=candidate,reference=ref,stratum=layer,development_incoming=len(values),target_RMSE_ratio=.95,normal80pct_power_incoming=needed,contrast_variance=variance,reference_MSE=float(np.average(err[:,k]**2,weights=ww)),caveat='conditional pilot normal approximation with variable weights; not guaranteed sufficient N, excludes source/refit/system and all joint gates'))
        for arm in ['X','XZ']:
            for layer in LAYERS:
                ref='traditional' if layer in LAYERS[:2] else 'direct_cal';limit=1.05 if ref=='traditional' else 1.01 if layer=='all' else 1.03
                match=next((r for r in pairs if r['role']==role and r['stratum']==layer and r['candidate']==arm and r['reference']==ref),None)
                tail=next((r for r in pairs if r['role']==role and r['stratum']==layer and r['candidate']==arm and r['reference']=='direct_cal'),None)
                gates.append(dict(role=role,arm=arm,stratum=layer,RMSE_upper95=match['high95'] if match else None,limit=limit,RMSE_pass=bool(match and match['high95'] is not None and match['high95']<=limit),tail_pass=bool(tail and all(tail[s+'_tail_high95_pp'] is not None and tail[s+'_tail_high95_pp']<=2 for s in ['total','positive','negative']))))
    table('metrics.tsv',points);table('paired.tsv',pairs);table('support.tsv',support);table('planning_support.tsv',power);table('paired_validation.tsv',validations);table('gates.tsv',gates)
    np.savez_compressed(ART/'predictions.npz',**policies)
    main_pairs=[r for r in pairs if r['candidate']=='XZ' and r['reference']=='X' and r['role'] in [2,3] and r['stratum'] in LAYERS[:2]]
    summary=dict(N=len(d['role']),active_N=int((d['role']>0).sum()),dimensions=dict(X=62,XZ=d['XZ'].shape[1]),native_available_N=int(d['z_available'].sum()),
        full_count_closed=bool(d['z_available'].all()),leading_identity_unknown_N=int(d['native_leading_unknown'].sum()),
        reserved_predictions=0,quarantine_predictions=0,
        joint={f'{role}_{a}':all(r['RMSE_pass'] and r['tail_pass'] for r in gates if r['role']==role and r['arm']==a) for role in [2,3] for a in ['X','XZ']},
        two_low_increment_supported=bool(len(main_pairs)==4 and all(r['high95'] is not None and r['high95']<1 for r in main_pairs)),
        X_vs_f0_max_abs_log_difference=float(np.nanmax(abs(policies['X']-policies['direct_cal']))),
        limitations=['original developed cohort, not independent confirmation','incoming proxy not full GENIE family','conditional incoming intervals exclude source/refit/research selection/real systems','no truth association as deployment feature','absence/unknown association not energy-quality deletion'])
    source_checks=[]
    for role in [2,3]:
        for run in sorted(set(d['run'][d['role']==role])):
            for layer,mask in masks(d).items():
                ix=np.flatnonzero((d['role']==role)&(d['run']==run)&mask)
                if not len(ix):continue
                w=weights(d['incoming'][ix]);e=np.log(d['truth_E_GeV'][ix]);a=policies['X'][ix]-e;b=policies['XZ'][ix]-e
                source_checks.append(dict(role=role,run=int(run),stratum=layer,N=len(ix),incoming=len(np.unique(d['incoming'][ix],axis=0)),X_log_RMSE=float(np.sqrt(np.average(a*a,weights=w))),XZ_log_RMSE=float(np.sqrt(np.average(b*b,weights=w))),MSE_delta=float(np.average(b*b-a*a,weights=w)),scope='conditional run-direction diagnostic; not new independent confirmation'))
    table('source_direction.tsv',source_checks)
    (OUT/'comparison_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary,flush=True)

def main():
 assert not ART.exists(),'formal fixed pair already started; never rerun for a better outcome'
 d=prepare();ART.mkdir(parents=True)
 with mp.get_context('fork').Pool(2) as pool:fits=pool.map(fit,[(arm,d) for arm in ['X','XZ']])
 (OUT/'fits.json').write_text(json.dumps(fits,indent=2)+'\n');evaluate(d)
if __name__=='__main__':main()
