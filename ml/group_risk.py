"""Stage68 direct regression with train-only group-risk dual updates."""
import json
import numpy as np
from audited_features import REPO,configuration,load
from expert_combination import begin,resources,save,masks

OUT=REPO/'workbook/stage68_energy_ml'
ART=REPO/'ml/artifacts/stage68'
LOW=['E50_100','E100_200']
COST={'all':1.01,'E200_inf':1.03,'pz50_100':1.03,'high_y':1.03,'unconfirmed':1.03}


def inputs():
    d,s,x=load();rows=s['row'];role=np.full(len(rows),'unused',dtype='<U6')
    role[d['train_eligible'][rows]]='train';role[d['cal_eligible'][rows]]='cal';role[d['partition'][rows]=='validation']='eval'
    use=role!='unused';row=rows[use]
    out={k:d[k][row] for k in ['truth_E_GeV','y_lepton','confirmed','source','group','component','incoming']}
    out.update(row=row,role=role[use],x=x[use],pz=d['reco_pz_GeV'][row],missing=np.isnan(x[use]).any(axis=1))
    assert [int((out['role']==r).sum()) for r in ['train','cal','eval']]==[41447,8440,14057]
    return out


def training_split(d,p,job):
    """Keep every held source; purge exact incoming reuse from training only."""
    tr=d['role']=='train'
    if job=='final':return tr,None,np.zeros(len(tr),bool)
    fold=np.full(len(tr),-1);fold[tr]=[p['fold_by_group'][str(g)] for g in d['group'][tr]]
    held=tr&(fold==int(job[-1]));candidate=tr&~held
    identities=set(map(tuple,d['incoming'][held]))
    purged=np.array([candidate[i] and tuple(v) in identities for i,v in enumerate(d['incoming'])])
    use=candidate&~purged
    assert not set(d['group'][use])&set(d['group'][held])
    assert not set(map(tuple,d['incoming'][use]))&identities
    return use,held,purged


def risks(pred,y,groups):return np.array([np.mean((pred[m]-y[m])**2) for m in groups])


def coefficients(groups,denominators,low_dual,cost_dual):
    """Normalized event weights; overlap contributions add, each group has its N."""
    dual=np.r_[low_dual,cost_dual];n=len(groups[0]);a=np.zeros(n)
    for mask,denom,multiplier in zip(groups,denominators,dual):
        assert mask.any() and denom>0
        a[mask]+=multiplier/(mask.sum()*denom)
    normal=a.mean();assert normal>0
    return a/normal,normal


def dual_step(low_dual,cost_dual,ratios,iteration,p):
    step=p['dual_step']/np.sqrt(1+iteration/p['dual_decay_rounds'])
    logits=np.log(low_dual)+step*np.clip(ratios[:2]-np.mean(ratios[:2]),-p['dual_increment_clip'],p['dual_increment_clip'])
    logits-=logits.max();q=np.exp(logits);q/=q.sum()
    q=np.maximum(q,p['low_probability_floor']);q/=q.sum()
    violation=ratios[2:]-np.array(list(COST.values()))**2
    raw=cost_dual+step*np.clip(violation,-p['dual_increment_clip'],p['dual_increment_clip'])
    return q,np.clip(raw,0,p['cost_dual_upper']),int((raw>p['cost_dual_upper']).sum()),int((abs(np.r_[ratios[:2]-np.mean(ratios[:2]),violation])>p['dual_increment_clip']).sum())


def fit_pair(x,y,pz,group_masks,p,destination,rounds=None):
    import xgboost as xgb
    rounds=p['rounds'] if rounds is None else rounds
    destination.mkdir(parents=True,exist_ok=True)
    params=dict(p['xgboost'],seed=p['seed'],base_score=float(y.mean()),boost_from_average=0)
    dm=xgb.DMatrix(x,label=y,feature_names=p['features'],nthread=p['request_cpus'])
    start=begin();C=xgb.train(params,dm,num_boost_round=rounds);c_pred=C.predict(dm).astype(float)
    C.save_model(destination/'C.ubj');c_resources=resources(start)
    masks_list=[group_masks[k] for k in LOW+list(COST)]
    mu=np.log(pz/.8);denom=np.r_[risks(mu,y,masks_list[:2]),risks(c_pred,y,masks_list[2:])]
    assert np.all(denom>0)
    R=xgb.Booster(params=params,cache=[dm]);q=np.full(2,.5);lam=np.ones(5)*p['initial_cost_dual']
    trajectory=[];start=begin()
    for iteration in range(rounds):
        pred=R.predict(dm,output_margin=True).astype(float)
        ratio=risks(pred,y,masks_list)/denom
        q,lam,caps,clips=dual_step(q,lam,ratio,iteration,p)
        weights,normal=coefficients(masks_list,denom,q,lam)
        # The 1/2 convention matches XGBoost's squared-error gradients.
        grad=(weights*(pred-y)).astype('float32');hess=weights.astype('float32')
        assert np.all(np.isfinite(grad)) and np.all(np.isfinite(hess)) and np.all(hess>=0)
        R.boost(dm,iteration,grad,hess)
        after=R.predict(dm,output_margin=True).astype(float);rr=risks(after,y,masks_list)/denom
        trajectory.append(dict(iteration=iteration+1,low_MSE_ratios=rr[:2].tolist(),cost_MSE_ratios=rr[2:].tolist(),
            worst_low_MSE_ratio=float(rr[:2].max()),max_cost_violation=float(max(0,np.max(rr[2:]-np.array(list(COST.values()))**2))),
            low_dual=q.tolist(),cost_dual=lam.tolist(),normalization_mean_unscaled=float(normal),
            event_weight_min=float(weights.min()),event_weight_max=float(weights.max()),event_weight_ESS=float(weights.sum()**2/(weights@weights)),
            capped_cost_updates=caps,clipped_dual_increments=clips))
    R.save_model(destination/'R.ubj');r_resources=resources(start)
    final=R.predict(dm).astype(float)
    for model in [C,R]:
        assert model.num_boosted_rounds()==rounds
        model.set_attr(feature_policy='F7_pz0_raw_v1',deployment_inputs=json.dumps(p['features']))
    # Re-save attributes and verify predictions from standalone reloaded models.
    for name,model in [('C',C),('R',R)]:
        model.save_model(destination/(name+'.ubj'))
        restored=xgb.Booster(params={'nthread':p['request_cpus']});restored.load_model(destination/(name+'.ubj'))
        np.testing.assert_array_equal(model.predict(dm),restored.predict(dm))
    diagnostics=dict(C_resources=c_resources,R_resources=r_resources,base_score=params['base_score'],params=params,
        group_order=LOW+list(COST),group_N=[int(m.sum()) for m in masks_list],risk_denominators=denom.tolist(),
        C_risks=risks(c_pred,y,masks_list).tolist(),R_risks=risks(final,y,masks_list).tolist(),
        C_low_MSE_ratios=(risks(c_pred,y,masks_list[:2])/denom[:2]).tolist(),
        final=trajectory[-1],trajectory=trajectory,rounds=rounds,model_reload_exact=True,
        checkpoint_policy='round400 only; no iterate selection, mixture, early stop or feasibility repair')
    return C,R,diagnostics
