"""One bounded Stage117 2x2; train-internal development, then locked evaluation."""
import json
import multiprocessing as mp
import resource
import time
import traceback

import numpy as np

from stage117_baselines import generate, mu_predict
from stage117_common import ART, IO, LAYERS, OUT, PROTECT, cached_inputs, masks, metrics, save, table
from stage117_folds import design, weights
from stage117_head import dictionary, predict, solve
from stage117_report import ARMS, report

G = None


def development_score(d,ids,pred,base,w):
    truth=np.log(d['truth_E_GeV'][ids]);groups=masks({k:v[ids] for k,v in d.items()})
    er=pred-truth;ref=base-truth;trad=np.log(d['pz'][ids]/.8)-truth;violation=[];low=[];rows=[]
    for name in LAYERS:
        m=groups[name];avg=lambda a:float(np.average(a[m],weights=w[m]))
        rmse=np.sqrt(avg(er**2));old=np.sqrt(avg(ref**2));t=np.sqrt(avg(trad**2))
        if name in LAYERS[:2]:low.append(rmse/t)
        if name in PROTECT:violation.append(max(rmse/old/PROTECT[name]-1,0))
        rel=np.expm1(er[m]);original=np.expm1(ref[m]);tail=[]
        for flag,rf in [(abs(rel)>.5,abs(original)>.5),(rel>.5,original>.5),(rel<-.5,original<-.5)]:
            delta=float(np.average(flag.astype(float)-rf.astype(float),weights=w[m]));tail.append(delta)
            violation.append(max(delta-.02,0))
        rows.append(dict(stratum=name,log_RMSE=rmse,baseline_RMSE=old,traditional_RMSE=t,
                         total_tail_delta_pp=tail[0]*100,positive_tail_delta_pp=tail[1]*100,negative_tail_delta_pp=tail[2]*100))
    return (max(violation),max(low)),rows


def fit_arm(name):
    d,x,train,pairs,full,inner,devbase,params,selected=G
    wall=time.perf_counter();cpu=time.process_time()
    source,kind=name.split('_');discovery,dev=pairs['outer0']
    ids=train if selected is not None else discovery
    base=full[source] if selected is not None else inner[source]
    label=name if selected is not None else name+'_dev'
    w=weights(d,ids);tree,leaves=dictionary(x,d,ids,base,w,kind,label,params)
    if selected is None:
        scores=[]
        for ntrees in [4,8]:
            cname=f'{label}{ntrees}';head,diag=solve(cname,leaves[:,:ntrees],d,ids,base,w)
            pred=devbase+predict(tree,head,x[dev]);score,rows=development_score(d,dev,pred,devbase,weights(d,dev))
            table(f'{cname}_development_risks.tsv',rows)
            scores.append(dict(trees=ntrees,violation=score[0],low_max=score[1],solve=diag))
        best=min(scores,key=lambda r:(r['violation'],r['low_max'],r['trees']))
        save(f'{name}_development.json',dict(arm=name,chosen_trees=best['trees'],candidates=scores,
            source_only_train_development=True,external_data_used=False))
        return name,best['trees']
    ntrees=selected[name];head,diag=solve(name,leaves[:,:ntrees],d,ids,base,w)
    # Prune unused suffix at persistence: selected capacity is actual deployment capacity.
    tree=tree[:ntrees];tree.save_model(ART/f'{name}_rules.ubj')
    result=dict(arm=name,trees=ntrees,source=source,kind=kind,solve=diag,
                CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-wall)
    save(f'{name}_fit.json',result)
    return name,result


def diagnostics(d, policies, train, bases):
    rows=[]
    for name,base in bases.items():
        for layer,m in masks({k:v[train] for k,v in d.items()}).items():
            if layer in LAYERS:
                rows.append(dict(baseline=name,stratum=layer,N=int(m.sum()),
                    **metrics(np.log(d['truth_E_GeV'][train[m]]),base[m],d['weight'][train[m]])))
    table('residual_source_risks.tsv',rows)
    rows=[]
    edges=np.array([-np.inf,50,100,200,400,800,1600,3200,6400,np.inf])
    for role,code in [('cal',2),('test',3)]:
        for name,p in policies.items():
            predicted=np.exp(p);bins=np.searchsorted(edges,predicted,side='right')-1
            for j in range(len(edges)-1):
                ids=np.flatnonzero((d['role']==code)&(bins==j))
                if len(ids):
                    w=d['weight'][ids];avg=lambda v:float(np.average(v,weights=w))
                    rows.append(dict(role=role,model=name,predicted_bin_low_GeV=edges[j],predicted_bin_high_GeV=edges[j+1],
                        N=len(ids),incoming=len(np.unique(d['key_id'][ids])),mean_predicted_GeV=avg(predicted[ids]),
                        mean_truth_GeV=avg(d['truth_E_GeV'][ids]),mean_log_error=avg(p[ids]-np.log(d['truth_E_GeV'][ids]))))
    table('calibration.tsv',rows)


def main():
    import xgboost as xgb
    global G
    start=time.perf_counter();cpu=time.process_time()
    assert json.loads((OUT/'fold_audit.json').read_text())['passed']
    assert not (ART/'candidates_locked.json').exists()
    d,mat,sub,pw=cached_inputs();x=mat['B'];train,fold,pairs,assignment=design(d)
    full,inner,devbase=generate(d,x[:,:62],train,pairs)
    params=json.loads((OUT.parent/'stage87_energy_ml/protocol.json').read_text())['baseline']['xgboost']
    G=d,x,train,pairs,full,inner,devbase,params,None
    with mp.get_context('fork').Pool(4) as pool:selected=dict(pool.map(fit_arm,ARMS))
    save('capacity_locked.json',dict(selected=selected,choices=[4,8],selected_inside_original_train_only=True))
    G=d,x,train,pairs,full,inner,devbase,params,selected
    with mp.get_context('fork').Pool(4) as pool:fitted=dict(pool.map(fit_arm,ARMS))
    lock=dict(arms=ARMS,capacity=selected,all_parameters_locked=True,
              external_forward_or_risk_before_lock=False,new_offset=False)
    (ART/'candidates_locked.json').write_text(json.dumps(lock,indent=2)+'\n');save('fits_frozen.json',lock)
    policies=dict(traditional=np.log(d['pz']/.8),direct_cal=d['base'])
    for name in ARMS:
        tree=xgb.Booster(params={'nthread':1});tree.load_model(ART/f'{name}_rules.ubj')
        head=json.loads((ART/f'{name}_head.json').read_text());correction=predict(tree,head,x)
        p=d['base'].copy();np.add(p,correction,out=p,where=correction!=0)
        assert np.isfinite(p).all();policies[name]=p
    policies['mu_only']=mu_predict(d,x[:,:62])
    np.savez_compressed(ART/'points.npz',row=d['row'],**{k:v for k,v in policies.items() if k not in ['traditional','direct_cal']})
    with np.load(ART/'points.npz') as z:
        for k in z.files:np.testing.assert_array_equal(z[k],d['row'] if k=='row' else policies[k])
    diagnostics(d,policies,train,dict(**full,final_deployment_anchor=d['base'][train]))
    decision=report(d,policies,sub,pw)
    # Baseline folds and unselected development artifacts are reproducible,
    # unnecessary intermediates. Keep compact train residuals and fit evidence.
    removed=[]
    for path in ART.iterdir():
        if path.suffix=='.ubj' and path.name not in [f'{a}_rules.ubj' for a in ARMS]:
            removed.append(dict(name=path.name,bytes=path.stat().st_size));path.unlink()
        elif '_dev' in path.name:
            removed.append(dict(name=path.name,bytes=path.stat().st_size));path.unlink()
    save('worker_cleanup.json',dict(removed=removed,bytes=sum(r['bytes'] for r in removed)))
    save('io.json',dict(files=IO,local_requested_bytes=sum(r['local_read_requested_bytes'] for r in IO),
                       local_returned_bytes=sum(r['local_read_returned_bytes'] for r in IO),physical_network_bytes='unmeasured'))
    save('resources.json',dict(worker_self_CPU_s=time.process_time()-cpu,worker_wall_s=time.perf_counter()-start,
        reaped_children_CPU_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
        self_max_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,GPU=0,
        note='nested costs; GNU outer CPU/wall authoritative; simultaneous process-tree peak unmeasured'))
    save('complete.json',dict(status='experiment_complete',actual_baseline_fits=18,dictionaries=8,
        convex_solves=24,arms=4,all_original_samples_K_roles_preserved=True,new_ROOT=False,new_production=False,decision=decision))
    print(json.dumps(decision,indent=2),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        save('failure.json',dict(error=repr(error),traceback=traceback.format_exc(),completed=False,no_automatic_retry=True))
        raise
