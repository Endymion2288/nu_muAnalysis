"""One fixed strong policy for the frozen curve and augmented candidate."""
import json
import multiprocessing as mp
import resource
import time

import numpy as np
import xgboost as xgb

from audited_features import configuration
from stage119_curve_common import ROOT,OUT,CACHE,load,weights,table

ART=ROOT/'ml/artifacts/stage119'
G=None


def fit(spec):
    name,old_ix,new_ix=spec;old,new,p=G;tick=time.perf_counter();cpu=time.process_time()
    x=np.concatenate([old['x'][old_ix],new['x'][new_ix]])
    y=np.log(np.concatenate([old['truth_E_GeV'][old_ix],new['truth_E_GeV'][new_ix]]))
    incoming=np.concatenate([old['incoming'][old_ix],new['incoming'][new_ix]])
    w=weights(incoming);names=configuration()['features'];train=xgb.DMatrix(x,label=y,weight=w,feature_names=names)
    old_use=np.flatnonzero(old['role']>0);new_use=np.flatnonzero(new['role']!=3)
    old_eval=xgb.DMatrix(old['x'][old_use],feature_names=names);new_eval=xgb.DMatrix(new['x'][new_use],feature_names=names)
    old_predictions=[];new_predictions=[]
    for seed in p['baseline']['seeds']:
        params=dict(p['baseline']['xgboost'],seed=seed,base_score=float(np.average(y,weights=w)),boost_from_average=0)
        model=xgb.train(params,train,num_boost_round=p['baseline']['rounds'])
        model.save_model(ART/f'{name}_{seed}.ubj')
        old_predictions.append(model.predict(old_eval).astype(float));new_predictions.append(model.predict(new_eval).astype(float))
    a=np.mean(old_predictions,axis=0);b=np.mean(new_predictions,axis=0)
    oc=old['role'][old_use]==2;offset=float(np.average(np.log(old['truth_E_GeV'][old_use][oc])-a[oc],weights=old['weight'][old_use][oc]))
    oldraw=np.full(len(old['role']),np.nan);newraw=np.full(len(new['role']),np.nan);oldraw[old_use]=a;newraw[new_use]=b
    np.savez_compressed(ART/f'{name}_predictions.npz',old_raw=oldraw,old_cal=oldraw+offset,new_raw=newraw,new_cal=newraw+offset)
    return dict(policy=name,old_train_N=len(old_ix),new_train_N=len(new_ix),train_proxy_families=len(np.unique(incoming,axis=0)),
        weight_sum=float(w.sum()),offset_log=offset,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
        peak_worker_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,parameters=params,rounds=p['baseline']['rounds'],seeds=p['baseline']['seeds'])


def control(old,new):
    selected=new['train_4N'];target={};oldcells=[]
    def cell(comp,e,y,z):
        return f'{comp}:E{np.searchsorted([100,200,1000],e,side="right")}:y{np.searchsorted([.8],y,side="right") if np.isfinite(y) and 0<=y<1 else 2}:z{int(z>=-1950)}'
    for g in np.unique(new['key_id'][selected]):
        i=np.flatnonzero(selected&(new['key_id']==g))[0];c=cell(new['component'][i],new['truth_E_GeV'][i],new['y_lepton'][i],new['vertex_z_mm'][i]);target[c]=target.get(c,0)+1
    groups={};train=np.flatnonzero((old['role']==1)&(old['vertex_z_mm']>=-2200));families={}
    for i in train:families.setdefault(tuple(old['incoming'][i]),[]).append(i)
    # Match the canonical FAMILY cells used by the new curve. Partitioning
    # response rows separately can count one incoming family in several cells.
    for key,views in families.items():
        i=views[0];c=cell(old['component'][i],old['truth_E_GeV'][i],old['y_lepton'][i],old['vertex_z_mm'][i])
        groups.setdefault(c,{})[key]=views
    rng=np.random.default_rng(20261105194);ids=[];rows=[];complete=True
    for c,n in sorted(target.items()):
        available=list(groups.get(c,{}));take=min(n,len(available));complete &= take==n
        order=rng.permutation(len(available))[:take]
        for i in order:ids.extend(groups[c][available[i]])
        rows.append(dict(cell=c,new_curve_max_families=n,old_available_families=len(available),old_selected_families=take))
    table('same_N_control_fixed.tsv',rows)
    if complete:
        assert len(np.unique(old['incoming'][ids],axis=0))==int(sum(target.values()))
        return np.array(ids,int)
    return None


def main():
    global G
    ART.mkdir(parents=True,exist_ok=True);tick=time.perf_counter();old=load('ntuples/energy_ml_stage119/old_input.npz');new=load('ntuples/energy_ml_stage119/curve_input.npz');p=json.loads((OUT/'curve_protocol.json').read_text())
    names=configuration()['features'];old_use=np.flatnonzero(old['role']>0);new_use=np.flatnonzero(new['role']!=3)
    # Frozen original model and offset, with exact original cache readback.
    raw=[];nr=[]
    for seed in p['baseline']['seeds']:
        model=xgb.Booster(params={'nthread':1});model.load_model(ROOT/f'ml/artifacts/stage87/direct_{seed}.ubj');assert model.feature_names==names
        raw.append(model.predict(xgb.DMatrix(old['x'][old_use],feature_names=names)).astype(float))
        nr.append(model.predict(xgb.DMatrix(new['x'][new_use],feature_names=names)).astype(float))
    raw=np.mean(raw,axis=0);nr=np.mean(nr,axis=0);cached=load('ml/artifacts/stage87/predictions.npz')
    np.testing.assert_array_equal(cached['row'],old_use);np.testing.assert_array_equal(raw,cached['direct_raw'])
    offsets=np.asarray(cached['direct_cal'])-raw;assert np.ptp(offsets)<1e-12;offset=float(offsets[0])
    baseold=np.full(len(old['role']),np.nan);basenew=np.full(len(new['role']),np.nan);baseold[old_use]=cached['direct_cal'];basenew[new_use]=nr+offset
    np.savez_compressed(ART/'reference_predictions.npz',old=baseold,new=basenew)
    tasks=[(f'curve_{factor}N',np.array([],int),np.flatnonzero(new[f'train_{factor}N'])) for factor in [1,2,4]]
    tasks.append(('augmented',np.flatnonzero(old['role']==1),np.flatnonzero((new['role']==1)&(new['kind']=='expansion'))))
    matched=control(old,new)
    if matched is not None:tasks.append(('old_same_N',matched,np.array([],int)))
    # Task list and all training memberships are fixed before any outcome fit.
    (OUT/'fit_task_lock.json').write_text(json.dumps(dict(tasks=[dict(name=n,old_rows=a.tolist(),new_rows=b.tolist()) for n,a,b in tasks],
        original_reference_exact=True,offset=offset,new_reserved_forward_N=0,control_comparison='same component/E/y/depth and N; old flux/year mixture differs, no pure randomized source effect'),indent=2)+'\n')
    G=old,new,p
    with mp.get_context('fork').Pool(min(5,len(tasks))) as pool:results=pool.map(fit,tasks)
    (OUT/'fits.json').write_text(json.dumps(dict(results=results,wall_s=time.perf_counter()-tick,
        original_reference_cache_exact=True,new_reserved_forward_N=0,old_quarantine_forward_N=0,GPU=0),indent=2)+'\n')
    print(results,flush=True)


if __name__=='__main__':main()
