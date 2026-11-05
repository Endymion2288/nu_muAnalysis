"""Paired fixed-policy energy risks, primary contrasts and independent checks."""
import csv
import multiprocessing as mp

import numpy as np

from stage115_common import LAYERS, ROOT, ci, draws, masks, metrics, save, table

G = None
PAIRS = [('A','direct_cal'),('A','traditional'),('B','direct_cal'),('B','traditional'),('B','A')]


def task(spec):
    role,layer=spec;d,policies,roles=G;v=roles[role];z=v['masks'][layer]
    ix=v['use'][z];w=v['weights'][z];gid=v['gid'][z];bw=v['draw'];nk=bw.shape[1]
    den=bw@np.bincount(gid,weights=w,minlength=nk);valid=den>0
    names=list(policies);y=np.log(d['truth_E_GeV'][ix]);err=np.column_stack([policies[k][ix]-y for k in names])
    agg=np.zeros((nk,len(names)));np.add.at(agg,gid,w[:,None]*err**2);boot=bw@agg
    support=dict(role=role,stratum=layer,N=len(ix),incoming=len(np.unique(d['key_id'][ix])),
                 weight_sum=float(w.sum()),ESS=float(w.sum()**2/(w@w)),
                 source_groups=len(np.unique(d['group'][ix])),connected_blocks=len(np.unique(d['block'][ix])))
    points=[]
    for j,k in enumerate(names):
        bounds=ci(np.sqrt(boot[valid,j]/den[valid]))
        points.append(dict(model=k,**support,**metrics(y,policies[k][ix],w),RMSE_low95=bounds[0],RMSE_high95=bounds[1]))
    rel=np.expm1(err);tails={}
    for sign,flags in [('total',abs(rel)>.5),('positive',rel>.5),('negative',rel<-.5)]:
        a=np.zeros_like(agg);np.add.at(a,gid,w[:,None]*flags);tails[sign]=(a.sum(0)/w.sum(),bw@a)
    paired=[];primary={}
    for candidate,reference in PAIRS:
        a,b=names.index(candidate),names.index(reference);good=valid&(boot[:,b]>0)
        rr=np.full(500,np.nan);rr[good]=np.sqrt(boot[good,a]/boot[good,b]);bounds=ci(rr)
        row=dict(candidate=candidate,reference=reference,**support,
            RMSE_ratio=float(np.sqrt(agg[:,a].sum()/agg[:,b].sum())),low95=bounds[0],high95=bounds[1],valid_draws=int(good.sum()))
        for sign,(central,bt) in tails.items():
            low,high=ci(100*(bt[good,a]-bt[good,b])/den[good])
            row.update({sign+'_tail_delta_pp':float(100*(central[a]-central[b])),
                        sign+'_tail_low95_pp':low,sign+'_tail_high95_pp':high})
        paired.append(row)
        if role=='cal_post' and layer in LAYERS[:2]: primary[(candidate,reference,layer)]=rr
    # Independent row-space dot products check every final-test comparison.
    checks=[]
    if role=='test' and layer in LAYERS:
        sw=bw[:,gid]*w[None,:];rowden=sw.sum(1);indloss=sw@err**2
        for r in paired:
            a,b=names.index(r['candidate']),names.index(r['reference']);ratio=ci(np.sqrt(indloss[:,a]/indloss[:,b]))
            delta=max(abs(ratio[0]-r['low95']),abs(ratio[1]-r['high95']))
            for sign,flags in [('total',abs(rel)>.5),('positive',rel>.5),('negative',rel<-.5)]:
                bounds=ci(100*(sw@(flags[:,a].astype(float)-flags[:,b].astype(float)))/rowden)
                delta=max(delta,abs(bounds[0]-r[sign+'_tail_low95_pp']),abs(bounds[1]-r[sign+'_tail_high95_pp']))
            assert delta<1e-10
            checks.append(dict(stratum=layer,candidate=r['candidate'],reference=r['reference'],interval_max_abs=delta))
    return points,paired,primary,checks


def report(d,policies,sub,pw):
    global G
    roles={};cal=np.flatnonzero(d['role']==2);test=np.flatnonzero(d['role']==3)
    for role,ix,w,seed in [('cal',cal,d['weight'][cal],2026110389),
        ('cal_post',cal[sub[cal]==2],pw[cal[sub[cal]==2]],2026110389),
        ('test',test,d['weight'][test],2026110390)]:
        sd={k:v[ix] for k,v in d.items()};keys,gid,bw=draws(sd,seed)
        np.testing.assert_allclose(np.bincount(gid,weights=w),1,atol=1e-12,rtol=0)
        roles[role]=dict(use=ix,weights=w,keys=keys,gid=gid,draw=bw,masks=masks(sd))
    G=d,policies,roles
    jobs=[(r,k) for r,v in roles.items() for k,m in v['masks'].items() if m.any()]
    with mp.get_context('fork').Pool(4) as pool: result=pool.map(task,jobs,chunksize=1)
    points=sum((r[0] for r in result),[]);paired=sum((r[1] for r in result),[])
    boot={k:v for r in result for k,v in r[2].items()};checks=sum((r[3] for r in result),[])
    primary=[]
    for a,b in [('B','direct_cal'),('B','A'),('A','direct_cal')]:
        values=np.maximum(*(boot[(a,b,k)] for k in LAYERS[:2]));lo,hi=ci(values)
        central=max(r['RMSE_ratio'] for r in paired if r['role']=='cal_post' and r['stratum'] in LAYERS[:2] and r['candidate']==a and r['reference']==b)
        # Independent row-space primary calculation on both groups and common draws.
        v=roles['cal_post'];ind=[]
        for layer in LAYERS[:2]:
            z=v['masks'][layer];ix=v['use'][z];sw=v['draw'][:,v['gid'][z]]*v['weights'][z][None,:]
            truth=np.log(d['truth_E_GeV'][ix]);ind.append(np.sqrt((sw@(policies[a][ix]-truth)**2)/(sw@(policies[b][ix]-truth)**2)))
        bounds=ci(np.maximum(*ind));error=max(abs(bounds[0]-lo),abs(bounds[1]-hi));assert error<1e-10
        primary.append(dict(candidate=a,reference=b,role='cal_post',statistic='max of two low-energy RMSE ratios',
            point=central,low95=lo,high95=hi,supported=hi is not None and hi<1,
            valid_draws=int(np.isfinite(values).sum()),independent_interval_max_abs=error))
    gates=[]
    for candidate in ['A','B']:
        for layer in LAYERS:
            ref='traditional' if layer in LAYERS[:2] else 'direct_cal';limit=1.05 if ref=='traditional' else 1.01 if layer=='all' else 1.03
            r=next(r for r in paired if r['role']=='test' and r['stratum']==layer and r['candidate']==candidate and r['reference']==ref)
            t=next(r for r in paired if r['role']=='test' and r['stratum']==layer and r['candidate']==candidate and r['reference']=='direct_cal')
            gates.append(dict(candidate=candidate,stratum=layer,reference=ref,RMSE_upper95=r['high95'],limit=limit,
                RMSE_pass=r['high95'] is not None and r['high95']<=limit,
                tail_pass=all(t[s+'_tail_high95_pp'] is not None and t[s+'_tail_high95_pp']<=2 for s in ['total','positive','negative']),
                **{s+'_tail_upper95_pp':t[s+'_tail_high95_pp'] for s in ['total','positive','negative']}))
    # Existing scalar controls independently establish reference/weight compatibility.
    prior=list(csv.DictReader((ROOT/'workbook/stage94_energy_ml/metrics.tsv').open(),delimiter='\t'))
    old={(r['role'],r['stratum'],r['policy']):r for r in prior if r['weighting']=='incoming'}
    controls=[]
    for row in points:
        r=old.get((row['role'],row['stratum'],row['model']))
        if r:
            for key in ['log_RMSE','median_bias_pct','mean_bias_pct','R68_pct','tail50_pct','positive_tail50_pct','negative_tail50_pct']:
                delta=abs(row[key]-float(r[key]));assert delta<1e-10
                controls.append(dict(role=row['role'],stratum=row['stratum'],model=row['model'],metric=key,abs_error=delta))
    assert controls
    train=d['role']==1;y=np.log(d['truth_E_GeV'][train]);groups=masks({k:v[train] for k,v in d.items()})
    trainpoints=[]
    for layer,z in groups.items():
        if z.any():
            for name,p in policies.items():
                trainpoints.append(dict(role='train_in_sample',stratum=layer,model=name,N=int(z.sum()),**metrics(y[z],p[train][z],d['weight'][train][z])))
    for n,rs in [('metrics.tsv',points),('paired.tsv',paired),('gates.tsv',gates),('primary.tsv',primary),
                 ('train_metrics.tsv',trainpoints),('independent_checks.tsv',checks),('old_controls.tsv',controls)]: table(n,rs)
    outcome=dict(primary=primary,final_joint={c:all(r['RMSE_pass'] and r['tail_pass'] for r in gates if r['candidate']==c) for c in ['A','B']},
        state_increment_supported=primary[0]['supported'] and primary[1]['supported'],
        primary_candidate='B',promotion=False,interval_scope='500 incoming-within-component conditional draws; excludes source/parent/refit/research-selection/real systems; developed cal/test, not blind')
    save('decision.json',outcome)
    save('measurement_validation.json',dict(passed=True,independent_final_test_comparisons=len(checks),
        independent_interval_max_abs=max(r['interval_max_abs'] for r in checks),
        independent_primary_comparisons=3,old_scalar_checks=len(controls),old_scalar_max_abs=max(r['abs_error'] for r in controls),
        all_original_eight_strata_final_gates=True,no_posthoc_offset_or_candidate_selection=True))
    plot(points)
    return outcome


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    layers=LAYERS[:3]+['pz50_100_trueE200','high_y'];fig,ax=plt.subplots(figsize=(9,4),layout='constrained')
    for name in ['traditional','direct_cal','A','B']:
        v=[next(r['log_RMSE'] for r in rows if r['role']=='test' and r['stratum']==k and r['model']==name) for k in layers]
        ax.plot(range(len(layers)),v,'o-',label=name)
    ax.set(xticks=range(len(layers)),xticklabels=['50–100 GeV','100–200 GeV','all','low pz, high E','high-y'],
           ylabel='Incoming-weighted log-RMSE',title='Developed test: fixed BDT + constrained state residuals')
    ax.legend();from stage115_common import OUT
    fig.savefig(OUT/'state_residual_risks.svg');plt.close(fig)
