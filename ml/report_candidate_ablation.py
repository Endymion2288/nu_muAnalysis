"""Stage96 paired point risks and tails on unchanged full roles, parallel by stratum."""
import argparse
import csv
import json
import multiprocessing as mp
import resource
import time

import numpy as np

from prepare_candidate_ablation import REPO,OUT,CACHE,arrays,save,cost
from report_resplit_energy import strata,metrics,incoming_draws

G=None


def table(name,rows):
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)


def masks(d):
    result=strata(d)
    result.update(X_pz50_100=d['pz']<100,X_pz100_200=(d['pz']>=100)&(d['pz']<200),X_pz200_plus=d['pz']>=200,
                  X_status_valid=~(d['input_missing']|d['wave_invalid']|d['fit_failure']|d['calo_invalid']),
                  X_candidates_available=d['candidate_available'],X_candidates_unavailable=~d['candidate_available'],
                  X_candidates_single=d['candidate_available']&(d['candidate_count']==1),
                  X_candidates_multiple=d['candidate_available']&(d['candidate_count']>1),
                  X_candidates_empty=d['candidate_available']&(d['candidate_count']==0))
    for name in ['calo','activity']:
        for j in [-1,0,1,2]:result[f'X_{name}_{j}']=d['X_'+name]==j
    for name in ['pi','k','charm']:result['component_'+name]=d['component']==name
    return result


def prepare():
    assert json.loads((OUT/'worker_completion.json').read_text())['new_fits']==2
    d=arrays(REPO/'ntuples/energy_ml_stage94/evaluation_input.npz')
    p=arrays(REPO/'ml/artifacts/stage96/predictions.npz');c=arrays(CACHE/'candidates.npz')
    np.testing.assert_array_equal(d['row'],p['row']);np.testing.assert_array_equal(d['row'],c['row'])
    d['candidate_available']=c['available'];d['candidate_count']=np.diff(c['offsets']);d['source']=c['source']
    old=arrays(REPO/'ml/artifacts/stage87/predictions.npz');ix=np.searchsorted(old['row'],d['row']);np.testing.assert_array_equal(old['row'][ix],d['row'])
    policies={k:v for k,v in p.items() if k!='row'}
    policies.update(traditional=np.log(d['pz']/.8),direct_cal=old['direct_cal'][ix],direct_raw=old['direct_raw'][ix],bounded_cal=old['bounded_cal'][ix])
    p94=arrays(REPO/'ml/artifacts/stage94/point_predictions.npz');np.testing.assert_array_equal(p94['row'],d['row'])
    with (REPO/'workbook/stage94_energy_ml/offsets.tsv').open() as f:offset={r['model']:float(r['offset_logE']) for r in csv.DictReader(f,delimiter='\t')}
    policies['stage94_C']=p94['C_2026110494'].astype(float)+offset['C_2026110494']
    policies['stage94_Eensemble']=p94['E_ensemble'].astype(float)+offset['E_ensemble']
    post=arrays(REPO/'ntuples/energy_ml_stage94/cal_partition.npz');cal=np.flatnonzero(d['role']==2);ii=np.searchsorted(post['row'],d['row'][cal]);np.testing.assert_array_equal(post['row'][ii],d['row'][cal])
    ip=cal[post['subrole'][ii]==2];pw=post['weight'][ii][post['subrole'][ii]==2];y=np.log(d['truth_E_GeV'])
    delta=offset['direct_raw']
    assert abs(delta-float(np.average(y[ip]-policies['direct_raw'][ip],weights=pw)))<1e-12
    policies['direct_raw_post']=policies['direct_raw']+delta
    oracle=np.full(len(y),np.nan)
    for role,code in [('cal',2),('test',3)]:
        z=arrays(REPO/f'ntuples/energy_ml_stage92/predictions_{role}.npz');use=d['role']==code;np.testing.assert_array_equal(z['row'],d['row'][use]);oracle[use]=z['accurate_quantiles'][:,2]
    policies['posterior92']=oracle
    # Verify offsets independently before any statistical comparisons.
    with (OUT/'offsets.tsv').open() as f:shifts=list(csv.DictReader(f,delimiter='\t'))
    for cell in ['A','B']:
        shift=float(next(r['offset_logE'] for r in shifts if r['cell']==cell))
        expected=float(np.average(y[ip]-policies[cell+'_raw'][ip],weights=pw));assert abs(expected-shift)<1e-12
        np.testing.assert_allclose(policies[cell+'_cal'],policies[cell+'_raw']+shift,rtol=0,atol=0)
    draws={}
    for code in [2,3]:
        use=np.flatnonzero(d['role']==code);sub={k:v[use] for k,v in d.items()}
        keys,gid,draw=incoming_draws(sub,2026110387+code)
        _,inv=np.unique(d['key_id'][use],return_inverse=True)
        np.testing.assert_allclose(np.bincount(inv,weights=d['weight'][use]),1,atol=1e-12)
        draws[code]=(use,keys,gid,draw)
    return d,policies,draws


def one(task):
    code,layer=task;d,policies,draws=G;use,keys,gid,draw=draws[code]
    sub={k:v[use] for k,v in d.items()};mask=masks(sub)[layer];ix=use[mask];w=d['weight'][ix];n=len(ix)
    support=dict(role='cal' if code==2 else 'test',stratum=layer,N=n,incoming=len(np.unique(d['key_id'][ix])),sources=len(np.unique(d['source'][ix])),weight_sum=float(w.sum()))
    if not n:return [],[],dict(**support,passed=True,empty=True,independent_values=0,max_key_sum_difference='not_applicable')
    y=np.log(d['truth_E_GeV'][ix]);names=list(policies);err=np.column_stack([policies[k][ix]-y for k in names]);small=gid[mask]
    assert np.isfinite(err).all()
    losskey=np.zeros((len(keys),len(names)));np.add.at(losskey,small,w[:,None]*err**2)
    # Different aggregation implementation for every squared-error column.
    check=np.column_stack([np.bincount(small,weights=w*err[:,j]**2,minlength=len(keys)) for j in range(len(names))])
    delta=float(abs(check-losskey).max());assert delta<1e-12
    losses=draw@losskey;den=draw@np.bincount(small,weights=w,minlength=len(keys));good=den>0
    points=[];paired=[]
    for j,name in enumerate(names):
        for weighting,ww in [('incoming',w),('record',np.ones(n))]:points.append(dict(policy=name,weighting=weighting,**support,**metrics(y,policies[name][ix],ww)))
    tails={};relative=np.expm1(err)
    for sign in ['total','positive','negative']:
        flag=abs(relative)>.5 if sign=='total' else relative>.5 if sign=='positive' else relative<-.5
        key=np.zeros_like(losskey);np.add.at(key,small,w[:,None]*flag);tails[sign]=(np.average(flag,axis=0,weights=w),draw@key)
    comparisons=[('B_cal','A_cal'),('B_raw','A_raw')]
    comparisons += [(cell+'_cal',ref) for cell in ['A','B'] for ref in ['traditional','direct_cal','direct_raw_post','posterior92','stage94_C','stage94_Eensemble']]
    for candidate,reference in comparisons:
        a,b=names.index(candidate),names.index(reference);valid=good&(losses[:,b]>0)
        rr=np.sqrt(losses[valid,a]/losses[valid,b]);ci=np.quantile(rr,[.025,.975]);point=float(np.sqrt(losskey[:,a].sum()/losskey[:,b].sum()))
        direct=float(np.sqrt(np.average(err[:,a]**2,weights=w)/np.average(err[:,b]**2,weights=w)));assert abs(point-direct)<1e-12
        r=dict(candidate=candidate,reference=reference,**support,RMSE_ratio=point,conditional_low95=float(ci[0]),conditional_high95=float(ci[1]),valid_draws=int(valid.sum()),source95='未测量',sparse=n<20)
        for sign,(estimate,bs) in tails.items():
            diff=(bs[valid,a]-bs[valid,b])/den[valid]*100;ci=np.quantile(diff,[.025,.975])
            r.update({sign+'_tail_delta_pp':float((estimate[a]-estimate[b])*100),sign+'_tail_low95_pp':float(ci[0]),sign+'_tail_high95_pp':float(ci[1])})
        paired.append(r)
    return points,paired,dict(**support,passed=True,empty=False,independent_values=len(keys)*len(names),max_key_sum_difference=delta)


def main(processes):
    global G
    start=time.perf_counter(),time.process_time();G=prepare();d,policies,draws=G
    tasks=[(code,name) for code in [2,3] for name in masks({k:v[d['role']==code] for k,v in d.items()})]
    tick=time.perf_counter()
    with mp.get_context('fork').Pool(processes) as pool:results=pool.map(one,tasks,chunksize=1)
    point=sum((r[0] for r in results),[]);paired=sum((r[1] for r in results),[]);checks=[r[2] for r in results]
    table('metrics.tsv',point);table('paired.tsv',paired);table('independent_checks.tsv',checks)
    gates=[]
    for cell in ['A_cal','B_cal']:
        for layer in ['E50_100','E100_200','all','E200_inf','pz50_100','pz50_100_trueE200','high_y','unconfirmed']:
            ref='traditional' if layer in ['E50_100','E100_200'] else 'direct_cal';limit=1.05 if ref=='traditional' else 1.01 if layer=='all' else 1.03
            r=next(p for p in paired if p['role']=='test' and p['candidate']==cell and p['reference']==ref and p['stratum']==layer)
            t=next(p for p in paired if p['role']=='test' and p['candidate']==cell and p['reference']=='direct_cal' and p['stratum']==layer)
            gates.append(dict(cell=cell,stratum=layer,reference=ref,upper95=r['conditional_high95'],limit=limit,RMSE_pass=r['conditional_high95']<=limit,
                              tail_pass=all(t[s+'_tail_high95_pp']<=2 for s in ['total','positive','negative']),**{s+'_tail_upper95_pp':t[s+'_tail_high95_pp'] for s in ['total','positive','negative']}))
    table('gates.tsv',gates)
    # All source views kept, including unavailable payload; no population prevalence claim.
    source_rows=[];sources=json.loads((OUT/'sources.json').read_text())
    for sid in np.unique(d['source']):
        use=d['source']==sid;role=int(d['role'][use][0]);assert np.unique(d['role'][use]).size==1
        y=np.log(d['truth_E_GeV'][use]);w=d['weight'][use]
        source_rows.append(dict(source=sources[sid]['source'],role=role,N=int(use.sum()),available_N=int(d['candidate_available'][use].sum()),multitrack_N=int((d['candidate_count'][use]>1).sum()),
                                A_raw_log_RMSE=float(np.sqrt(np.average((policies['A_raw'][use]-y)**2,weights=w))),B_raw_log_RMSE=float(np.sqrt(np.average((policies['B_raw'][use]-y)**2,weights=w)))))
    table('source_support.tsv',source_rows)
    validate_saved(point,paired)
    plot(point,paired)
    child=resource.getrusage(resource.RUSAGE_CHILDREN)
    save('report_completion.json',dict(passed=True,new_fits=2,roles={str(k):int((d['role']==k).sum()) for k in [1,2,3]},
          processes=processes,tasks=len(tasks),parallel_wall_s=time.perf_counter()-tick,child_CPU_s=child.ru_utime+child.ru_stime,
          metric_rows=len(point),paired_rows=len(paired),bootstrap_repeats=500,point_tail_joint_pass={cell:all(r['RMSE_pass'] and r['tail_pass'] for r in gates if r['cell']==cell) for cell in ['A_cal','B_cal']},
          uncertainty='component incoming conditional; shared views move together, no source/retraining/systematic/research-selection coverage',probability_metrics='not defined for point-only outputs',model_promotion=False,**cost(start)))
    print((OUT/'report_completion.json').read_text(),flush=True)


def validate_saved(points,paired):
    # Reproduce previously published point controls on exactly the same roles/weights.
    with (REPO/'workbook/stage94_energy_ml/metrics.tsv').open() as f:old=list(csv.DictReader(f,delimiter='\t'))
    lookup={(r['role'],r['stratum'],r['weighting'],r['policy']):r for r in old};n=0;maximum=0.
    aliases=dict(stage94_C='C_2026110494_cal',stage94_Eensemble='E_ensemble_cal')
    for row in points:
        name=aliases.get(row['policy'],row['policy']);key=(row['role'],row['stratum'],row['weighting'],name)
        if row['policy'].startswith(('A_','B_')) or key not in lookup:continue
        for field in ['log_RMSE','median_bias_pct','mean_bias_pct','R68_pct','tail50_pct','positive_tail50_pct','negative_tail50_pct']:
            delta=abs(row[field]-float(lookup[key][field]));maximum=max(maximum,delta);assert delta<1e-10;n+=1
    for cell in ['A','B']:
        with (OUT/f'learning_{cell}.tsv').open() as f:curve=list(csv.DictReader(f,delimiter='\t'))
        fit=json.loads((OUT/f'fit_{cell}.json').read_text());best=int(min(curve,key=lambda r:float(r['cal_select_logMSE']))['epoch'])
        assert best==fit['best_epoch'] and len(curve)*5==fit['epochs']
        assert fit['epochs']==300 or fit['epochs']-best>=30
        assert fit['optimizer_steps']==46*fit['epochs'] and fit['parameters']==23809
    assert json.loads((OUT/'before_test.json').read_text())['new_test_predictions']==0
    save('validation.json',dict(passed=True,old_control_values_reproduced=n,max_old_control_difference=maximum,
         new_fits=2,best_checkpoint_and_offsets_checked=True,all_rows_retained=True,new_probability_claim=False))


def plot(points,paired):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    groups=['E50_100','E100_200','all','pz50_100_trueE200','high_y','unconfirmed'];x=np.arange(len(groups))
    fig,ax=plt.subplots(1,3,figsize=(14,4.4),layout='constrained')
    for name in ['traditional','direct_cal','posterior92','stage94_Eensemble','A_cal','B_cal']:
        r=[next(p for p in points if p['role']=='test' and p['stratum']==g and p['weighting']=='incoming' and p['policy']==name)['log_RMSE'] for g in groups]
        ax[0].plot(x,r,'o-',label=name,ms=3)
    r=[next(p for p in paired if p['role']=='test' and p['stratum']==g and p['candidate']=='B_cal' and p['reference']=='A_cal') for g in groups]
    yy=np.array([p['RMSE_ratio'] for p in r]);lo=np.array([p['conditional_low95'] for p in r]);hi=np.array([p['conditional_high95'] for p in r])
    ax[1].errorbar(x,yy,yerr=np.maximum(0,np.vstack([yy-lo,hi-yy])),fmt='o',capsize=3);ax[1].axhline(1,color='grey',ls='--')
    for cell in ['A','B']:
        with (OUT/f'learning_{cell}.tsv').open() as f:r=list(csv.DictReader(f,delimiter='\t'))
        ax[2].plot([int(p['epoch']) for p in r],[float(p['cal_select_logMSE'])**.5 for p in r],label=cell)
    for a in ax[:2]:a.set_xticks(x,groups,rotation=35)
    ax[0].set(ylabel='Incoming-weighted log-RMSE',title='Developed-pool test risk');ax[0].legend(fontsize=7)
    ax[1].set(ylabel='B / A log-RMSE',title='New candidate input: conditional95%')
    ax[2].set(xlabel='Epoch',ylabel='cal_select log-RMSE',title='Fixed model, one seed per cell');ax[2].legend()
    for a in ax:a.grid(axis='y',alpha=.15)
    p=OUT/'candidate_ablation.svg';fig.savefig(p);p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n');plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--processes',type=int,default=8);a=p.parse_args();main(a.processes)
