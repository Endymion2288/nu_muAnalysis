"""Independent saved-output stage94 arithmetic/bootstrap audit using four CPU processes."""
import csv
import json
import multiprocessing as mp

import numpy as np

from audited_features import REPO
from support_augmentation import arrays,save,table,begin,resources

OUT=REPO/'workbook/stage94_energy_ml'
CACHE=REPO/'ntuples/energy_ml_stage94'
ART=REPO/'ml/artifacts/stage94'
G=None


def read(name):return list(csv.DictReader((OUT/(name+'.tsv')).open(),delimiter='\t'))


def task(args):
    role,layer=args;d,policies,points,paired=G;m=d['role']=={'cal':2,'test':3}[role]
    e=d['truth_E_GeV'];p=d['pz'];f=d['y_lepton'];masks=dict(all=np.ones(len(e),bool),E50_100=(e>=50)&(e<100),E100_200=(e>=100)&(e<200),E200_inf=e>=200,pz50_100=p<100,pz50_100_trueE200=(p<100)&(e>=200),high_y=d['label_physical']&(f>=.8),unconfirmed=~d['confirmed'])
    selected=m&masks[layer];ix=np.flatnonzero(selected);w=d['weight'][ix];y=np.log(e[ix]);count=0;maximum=0.
    def check(a,b):
        nonlocal count,maximum
        diff=abs(float(a)-float(b));assert diff<2e-9,(role,layer,a,b,diff);count+=1;maximum=max(maximum,diff)
    # Build the fixed component/incoming draw matrix independently.
    keys,first,inverse=np.unique(d['key_id'][m],return_index=True,return_inverse=True);component=d['component'][m][first]
    rng=np.random.default_rng(2026110387+{'cal':2,'test':3}[role]);draw=np.zeros((500,len(keys)),np.int16)
    for c in sorted(set(component)):
        ids=np.flatnonzero(component==c);draw[:,ids]=rng.multinomial(len(ids),np.ones(len(ids))/len(ids),size=500)
    gid=inverse[masks[layer][m]];den=np.dot(draw,np.bincount(gid,weights=w,minlength=len(keys)))
    for r in points:
        if r['role']!=role or r['stratum']!=layer:continue
        err=policies[r['policy']][ix]-y;ww=w if r['weighting']=='incoming' else np.ones(len(ix));rel=np.exp(err)-1
        order=np.argsort(rel,kind='stable');q=np.interp([.16,.5,.84],(np.cumsum(ww[order])-ww[order]/2)/ww.sum(),rel[order])
        for key,value in zip(['log_RMSE','median_bias_pct','mean_bias_pct','R68_pct','tail50_pct','positive_tail50_pct','negative_tail50_pct'],
            [np.sqrt(np.dot(ww,err*err)/ww.sum()),q[1]*100,np.dot(ww,rel)/ww.sum()*100,(q[2]-q[0])*50,np.dot(ww,abs(rel)>.5)/ww.sum()*100,np.dot(ww,rel>.5)/ww.sum()*100,np.dot(ww,rel<-.5)/ww.sum()*100]):check(r[key],value)
    # Per-key bincount is separate from reporter scatter-matrix implementation.
    names=list(policies);error={k:policies[k][ix]-y for k in names}
    loss={k:draw@np.bincount(gid,weights=w*v*v,minlength=len(keys)) for k,v in error.items()}
    tails={}
    for name,v in error.items():
        rel=np.expm1(v);tails[name]={t:(draw@np.bincount(gid,weights=w*flag,minlength=len(keys))) for t,flag in [('total',abs(rel)>.5),('positive',rel>.5),('negative',rel<-.5)]}
    for r in paired:
        if r['role']!=role or r['stratum']!=layer:continue
        a,b=r['candidate'],r['reference'];good=(den>0)&(loss[b]>0);ci=np.percentile(np.sqrt(loss[a][good]/loss[b][good]),[2.5,97.5]);check(r['conditional_low95'],ci[0]);check(r['conditional_high95'],ci[1]);check(r['RMSE_ratio'],np.sqrt(np.dot(w,error[a]**2)/np.dot(w,error[b]**2)))
        for sign in ['total','positive','negative']:
            bs=(tails[a][sign][good]-tails[b][sign][good])/den[good]*100;ci=np.percentile(bs,[2.5,97.5]);check(r[sign+'_tail_low95_pp'],ci[0]);check(r[sign+'_tail_high95_pp'],ci[1])
    return dict(role=role,stratum=layer,checked_values=count,max_absolute_difference=maximum,passed=True)


def main():
    start=begin();d=arrays(CACHE/'evaluation_input.npz');raw=arrays(ART/'point_predictions.npz');base=arrays(REPO/'ml/artifacts/stage87/predictions.npz');ib=np.searchsorted(base['row'],d['row']);np.testing.assert_array_equal(base['row'][ib],d['row'])
    policies=dict(traditional=np.log(d['pz']/.8),direct_raw=base['direct_raw'][ib],direct_cal=base['direct_cal'][ib],bounded_cal=base['bounded_cal'][ib]);offsets=read('offsets');offset={r['model']:float(r['offset_logE']) for r in offsets}
    part=arrays(CACHE/'cal_partition.npz');cal=np.flatnonzero(d['role']==2);ip=np.searchsorted(part['row'],d['row'][cal]);post=cal[part['subrole'][ip]==2];ww=part['weight'][ip][part['subrole'][ip]==2];yy=np.log(d['truth_E_GeV'])
    for name,v in raw.items():
        if name=='row':continue
        assert abs(np.dot(ww,yy[post]-v[post])/ww.sum()-offset[name])<1e-12
        policies[name+'_raw']=v;policies[name+'_cal']=v+offset[name]
    for name in ['traditional','direct_raw']:policies[name+'_post']=policies[name]+offset[name]
    old=np.full(len(yy),np.nan)
    for role,code in [('cal',2),('test',3)]:
        a=arrays(REPO/f'ntuples/energy_ml_stage92/predictions_{role}.npz');m=d['role']==code;np.testing.assert_array_equal(a['row'],d['row'][m]);old[m]=a['accurate_quantiles'][:,2]
    policies['posterior92']=old
    # Match float64 calibration arithmetic, not NumPy float32 scalar addition.
    for name,v in raw.items():
        if name!='row':policies[name+'_cal']=v.astype(float)+offset[name]
    points=read('metrics');paired=read('paired')
    global G
    G=(d,policies,points,paired)
    tasks=[(r,s) for r in ['cal','test'] for s in ['all','E50_100','E100_200','E200_inf','pz50_100','pz50_100_trueE200','high_y','unconfirmed']]
    with mp.get_context('fork').Pool(4) as pool:checks=pool.map(task,tasks)
    table(OUT/'independent_validation.tsv',checks)
    # Exact original baseline table closure on same split/weights, no refit.
    baseline=list(csv.DictReader((REPO/'workbook/stage87_energy_ml/metrics.tsv').open(),delimiter='\t'));baseline_count=0;baseline_max=0.
    index={(r['role'],r['stratum'],r['policy'],r['weighting']):r for r in baseline}
    for r in points:
        key=tuple(r[k] for k in ['role','stratum','policy','weighting'])
        if key not in index or r['policy'] not in ['traditional','direct_raw','direct_cal','bounded_cal']:continue
        for name in ['log_RMSE','median_bias_pct','mean_bias_pct','R68_pct','tail50_pct','positive_tail50_pct','negative_tail50_pct']:
            diff=abs(float(r[name])-float(index[key][name]));assert diff<1e-9;baseline_count+=1;baseline_max=max(baseline_max,diff)
    import resource
    u=resource.getrusage(resource.RUSAGE_CHILDREN)
    save(OUT/'independent_validation.json',dict(passed=True,independent_values=sum(r['checked_values'] for r in checks),max_difference=max(r['max_absolute_difference'] for r in checks),baseline_values=baseline_count,baseline_max_difference=baseline_max,post_offsets_reproduced=True,processes=4,child_CPU_s=u.ru_utime+u.ru_stime,**resources(start)))
    print((OUT/'independent_validation.json').read_text(),flush=True)


if __name__=='__main__':main()
