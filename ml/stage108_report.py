"""Eight-process original paired incoming-conditional risk; no fits or model forwards."""
import csv
import json
import multiprocessing as mp
import resource
import time
from pathlib import Path

import numpy as np
from report_resplit_energy import incoming_draws,metrics
from stage99_report import masks
from support_augmentation import arrays,save,table

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage108_energy_ml';ART=ROOT/'ml/artifacts/stage108'
LAYERS=['E50_100','E100_200','all','E200_inf','pz50_100','pz50_100_trueE200','high_y','unconfirmed']
NEW=[c+'_'+s for c in ['A','B','C'] for s in ['raw','cal']]
G=None


def ci(values):
    values=np.asarray(values);values=values[np.isfinite(values)]
    return [float(v) for v in np.quantile(values,[.025,.975])]


def task(spec):
    role,layer=spec;d,policies,roles=G;v=roles[role];mask=v['masks'][layer]
    ix=v['use'][mask];w=v['weights'][mask];gid=v['gid'][mask];draw=v['draw'];nk=len(v['keys'])
    den=draw@np.bincount(gid,weights=w,minlength=nk);valid=den>0
    support=dict(role=role,stratum=layer,N=len(ix),incoming=len(np.unique(gid)),weight_sum=float(w.sum()),
        source_groups=len(np.unique(d['group'][ix])),connected_blocks=len(np.unique(d['block'][ix])))
    names=list(policies);truth=np.log(d['truth_E_GeV'][ix]);errors=np.column_stack([policies[n][ix]-truth for n in names])
    agg=np.zeros((nk,len(names)));np.add.at(agg,gid,w[:,None]*errors**2);boot=draw@agg
    points=[]
    for j,name in enumerate(names):
        lo,hi=ci(np.sqrt(boot[valid,j]/den[valid]))
        points.append(dict(model=name,**support,**metrics(truth,policies[name][ix],w),RMSE_low95=lo,RMSE_high95=hi))
    tails={};rel=np.expm1(errors)
    for sign,flag in [('total',abs(rel)>.5),('positive',rel>.5),('negative',rel<-.5)]:
        a=np.zeros_like(agg);np.add.at(a,gid,w[:,None]*flag);tails[sign]=(a.sum(0)/w.sum(),draw@a)
    paired=[];primary={}
    for candidate in NEW:
        j=names.index(candidate)
        refs=['traditional','direct_cal']
        if candidate.startswith('B_'):refs+=['A_'+candidate.split('_')[1]]
        if candidate.startswith('C_'):refs+=['A_'+candidate.split('_')[1],'B_'+candidate.split('_')[1]]
        for ref in refs:
            b=names.index(ref);good=valid&(boot[:,b]>0);ratio=np.sqrt(boot[good,j]/boot[good,b]);lo,hi=ci(ratio)
            row=dict(candidate=candidate,reference=ref,**support,RMSE_ratio=float(np.sqrt(agg[:,j].sum()/agg[:,b].sum())),low95=lo,high95=hi,valid_draws=int(good.sum()),interval_scope='component-stratified incoming conditional; no source/refit/calibration/research-selection/system coverage')
            for sign,(central,bt) in tails.items():
                lo,hi=ci(100*(bt[good,j]-bt[good,b])/den[good])
                row.update({sign+'_tail_delta_pp':float(100*(central[j]-central[b])),sign+'_tail_low95_pp':lo,sign+'_tail_high95_pp':hi})
            paired.append(row)
            if role=='cal_post' and layer in LAYERS[:2] and candidate=='C_cal' and ref=='A_cal':
                assert good.all();primary[layer]=ratio
    return points,paired,primary


def validate(paired,primary):
    d,policies,roles=G;checks=[];v=roles['test']
    # Independent record-space expansion rather than incoming aggregation.
    for layer in LAYERS:
        z=v['masks'][layer];ix=v['use'][z];sw=v['draw'][:,v['gid'][z]]*v['weights'][z][None,:];den=sw.sum(1)
        y=np.log(d['truth_E_GeV'][ix]);ref='traditional' if layer in LAYERS[:2] else 'direct_cal'
        for candidate in NEW:
            err=policies[candidate][ix]-y
            r=next(r for r in paired if r['role']=='test' and r['stratum']==layer and r['candidate']==candidate and r['reference']==ref)
            bounds=ci(np.sqrt((sw@err**2)/(sw@(policies[ref][ix]-y)**2)))
            checks.append(dict(candidate=candidate,stratum=layer,metric='RMSE',max_abs_error=max(abs(bounds[0]-r['low95']),abs(bounds[1]-r['high95']))))
            r=next(r for r in paired if r['role']=='test' and r['stratum']==layer and r['candidate']==candidate and r['reference']=='direct_cal')
            rel=np.expm1(err);dr=np.expm1(policies['direct_cal'][ix]-y)
            for sign,a,b in [('total',abs(rel)>.5,abs(dr)>.5),('positive',rel>.5,dr>.5),('negative',rel<-.5,dr<-.5)]:
                bounds=ci(100*(sw@(a.astype(float)-b.astype(float)))/den)
                checks.append(dict(candidate=candidate,stratum=layer,metric=sign+'_tail',max_abs_error=max(abs(bounds[0]-r[sign+'_tail_low95_pp']),abs(bounds[1]-r[sign+'_tail_high95_pp']))))
    v=roles['cal_post'];ratios=[]
    for layer in LAYERS[:2]:
        z=v['masks'][layer];ix=v['use'][z];sw=v['draw'][:,v['gid'][z]]*v['weights'][z][None,:];y=np.log(d['truth_E_GeV'][ix])
        ratios.append(np.sqrt((sw@(policies['C_cal'][ix]-y)**2)/(sw@(policies['A_cal'][ix]-y)**2)))
    bounds=ci(np.maximum(*ratios));pe=max(abs(bounds[0]-primary['low95']),abs(bounds[1]-primary['high95']))
    assert pe<1e-10 and max(r['max_abs_error'] for r in checks)<1e-10
    table(OUT/'independent_gate_checks.tsv',checks)
    return dict(primary_max_abs_error=pe,gate_checks=len(checks),gate_max_abs_error=max(r['max_abs_error'] for r in checks))


def main():
    global G
    start=time.perf_counter(),time.process_time()
    freeze=json.loads((OUT/'before_test.json').read_text());assert freeze['checkpoints_and_offsets_frozen']
    full=arrays(ROOT/'ntuples/energy_ml_stage94/evaluation_input.npz');sel=np.isin(full['role'],[2,3]);d={k:v[sel] for k,v in full.items()}
    point=arrays(ART/'predictions.npz');ix=np.searchsorted(point['row'],d['row']);np.testing.assert_array_equal(point['row'][ix],d['row'])
    base=arrays(ROOT/'ml/artifacts/stage87/predictions.npz');ib=np.searchsorted(base['row'],d['row']);np.testing.assert_array_equal(base['row'][ib],d['row'])
    for k in ['role','weight','truth_E_GeV','pz']:np.testing.assert_array_equal(d[k],base[k][ib])
    split=arrays(ROOT/'ntuples/energy_ml_stage87/split.npz')
    for k in ['key_id','role','weight']:np.testing.assert_array_equal(d[k],split[k][d['row']])
    assert len(d['row'])==24801 and [int(d['input_missing'][d['role']==r].sum()) for r in [2,3]]==[6,5]
    policies=dict(traditional=np.log(d['pz']/.8),direct_cal=base['direct_cal'][ib])
    policies.update({k:point[k][ix] for k in NEW})
    for k in NEW:assert np.isfinite(policies[k]).all()
    d['geometry_available']=point['geometry_available'][ix]
    d['geometry_empty']=d['geometry_available']&(point['point_count'][ix]==0)
    cal=np.flatnonzero(d['role']==2);part=arrays(ROOT/'ntuples/energy_ml_stage94/cal_partition.npz');ip=np.searchsorted(part['row'],d['row'][cal]);np.testing.assert_array_equal(part['row'][ip],d['row'][cal])
    post=cal[part['subrole'][ip]==2];pw=part['weight'][ip][part['subrole'][ip]==2];assert len(post)==5746
    roles={}
    for role,use,w,seed in [('cal',cal,d['weight'][cal],2026110389),('cal_post',post,pw,2026110389),('test',np.flatnonzero(d['role']==3),d['weight'][d['role']==3],2026110390)]:
        sub={k:v[use] for k,v in d.items()};keys,gid,draw=incoming_draws(sub,seed);np.testing.assert_allclose(np.bincount(gid,weights=w),1.,atol=1e-12)
        layers=masks(sub);layers.update(geometry_missing=~sub['geometry_available'],geometry_empty=sub['geometry_empty'])
        roles[role]=dict(use=use,weights=w,keys=keys,gid=gid,draw=draw,masks=layers)
    G=d,policies,roles;jobs=[(role,layer) for role,v in roles.items() for layer,z in v['masks'].items() if z.any()]
    tick=time.perf_counter()
    with mp.get_context('fork').Pool(8) as pool:result=pool.map(task,jobs,chunksize=1)
    poolwall=time.perf_counter()-tick;rows=sum((r[0] for r in result),[]);paired=sum((r[1] for r in result),[]);pb={k:v for r in result for k,v in r[2].items()}
    centers=[next(r['RMSE_ratio'] for r in paired if r['role']=='cal_post' and r['stratum']==layer and r['candidate']=='C_cal' and r['reference']=='A_cal') for layer in LAYERS[:2]]
    lo,hi=ci(np.maximum(*(pb[k] for k in LAYERS[:2])))
    primary=dict(statistic='max of E50_100 and E100_200 RMSE C_cal/A_cal',role='cal_post',point=max(centers),low95=lo,high95=hi,supported=hi<1,bootstrap_replicates=500,conditional_only=True)
    checks=validate(paired,primary)
    oldrows=list(csv.DictReader((ROOT/'workbook/stage94_energy_ml/metrics.tsv').open(),delimiter='\t'));oldmap={(r['role'],r['stratum'],r['policy']):r for r in oldrows if r['weighting']=='incoming'}
    control=[]
    for r in rows:
        prev=oldmap.get((r['role'],r['stratum'],r['model'])) if r['model'] in ['traditional','direct_cal'] else None
        if prev:
            for k in ['log_RMSE','median_bias_pct','mean_bias_pct','R68_pct','tail50_pct','positive_tail50_pct','negative_tail50_pct']:
                err=abs(r[k]-float(prev[k]));assert err<1e-10;control.append(dict(role=r['role'],stratum=r['stratum'],model=r['model'],metric=k,abs_error=err))
    assert control
    gates=[]
    for candidate in NEW:
        for layer in LAYERS:
            ref='traditional' if layer in LAYERS[:2] else 'direct_cal';limit=1.05 if layer in LAYERS[:2] else 1.01 if layer=='all' else 1.03
            r=next(r for r in paired if r['role']=='test' and r['stratum']==layer and r['candidate']==candidate and r['reference']==ref)
            t=next(r for r in paired if r['role']=='test' and r['stratum']==layer and r['candidate']==candidate and r['reference']=='direct_cal')
            gates.append(dict(candidate=candidate,stratum=layer,reference=ref,upper95=r['high95'],limit=limit,RMSE_pass=r['high95']<=limit,tail_pass=all(t[s+'_tail_high95_pp']<=2 for s in ['total','positive','negative']),**{s+'_tail_upper95_pp':t[s+'_tail_high95_pp'] for s in ['total','positive','negative']}))
    for name,v in [('points.tsv',rows),('paired.tsv',paired),('gates.tsv',gates),('old_controls.tsv',control)]:table(OUT/name,v)
    decision=dict(primary=primary,final_joint_pass={c:all(r['RMSE_pass'] and r['tail_pass'] for r in gates if r['candidate']==c) for c in NEW},promotion=False,new_supervised_fits=3,pretraining_runs=1,no_automatic_followup=True,source_refit_systematic_independent_confirmation=False)
    save(OUT/'decision.json',decision)
    save(OUT/'report_validation.json',dict(passed=True,**checks,old_scalar_checks=len(control),old_scalar_max_abs_error=max(r['abs_error'] for r in control),roles={k:dict(records=len(v['use']),incoming=len(v['keys']),weight_sum=float(v['weights'].sum())) for k,v in roles.items()},saved_points_preserved=True,no_new_fit_or_calibration=True))
    plot(rows)
    children=resource.getrusage(resource.RUSAGE_CHILDREN)
    save(OUT/'report_complete.json',dict(passed=True,processes=8,tasks=len(jobs),pool_wall_s=poolwall,child_CPU_s=children.ru_utime+children.ru_stime,self_CPU_s=time.process_time()-start[1],wall_s=time.perf_counter()-start[0],peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024))
    print(json.dumps(decision,indent=2),flush=True)


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,4),layout='constrained');layers=LAYERS[:3]+['pz50_100_trueE200','high_y']
    for candidate in ['traditional','direct_cal','A_cal','B_cal','C_cal']:
        vals=[next(r for r in rows if r['role']=='test' and r['stratum']==layer and r['model']==candidate) for layer in layers]
        ax.errorbar(range(len(layers)),[r['log_RMSE'] for r in vals],yerr=[[r['log_RMSE']-r['RMSE_low95'] for r in vals],[r['RMSE_high95']-r['log_RMSE'] for r in vals]],marker='o',capsize=2,label=candidate)
    ax.set(xticks=range(len(layers)),xticklabels=['50–100 GeV','100–200 GeV','all','low pz, high E','high-y'],ylabel='Incoming-weighted log-RMSE',title='Developed test: full points, local relations and masked-plane pretraining');ax.legend(fontsize=8)
    fig.savefig(OUT/'point_relation.svg');plt.close(fig)


if __name__=='__main__':main()
