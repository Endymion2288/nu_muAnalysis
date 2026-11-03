"""Independent stage87 identity/split/weighted risks and conditional interval QA."""
import csv
import json

import numpy as np

from support_augmentation import arrays,save,begin,resources
from resplit_energy import OUT,CACHE,ART


def validate():
    start=begin();d=arrays(CACHE/'input.npz');v=arrays(ART/'predictions.npz');s=arrays(CACHE/'split.npz')
    p=json.loads((OUT/'protocol.json').read_text());bootstrap=arrays(ART/'bootstrap.npz')
    for key in s:np.testing.assert_array_equal(d[key],s[key])
    for key in d:
        if key!='x':np.testing.assert_array_equal(d[key],v[key])
    source_roles={};rng=np.random.default_rng(p['split_seed'])
    for comp in ['pi','k','charm']:
        groups=sorted(set(g for g in d['group'] if g.startswith(comp+':')));ordered=rng.permutation(groups)
        n=max(1,int(round(.15*len(groups))))
        for j,g in enumerate(ordered):source_roles[g]=3 if j<n else 2 if j<2*n else 1
    proposed=np.array([source_roles[g] for g in d['group']]);np.testing.assert_array_equal(proposed,d['initial_role'])
    high={}
    for key,role in zip(d['key_id'],proposed):high[int(key)]=max(high.get(int(key),0),int(role))
    expected=np.array([r if r==high[int(k)] else 0 for r,k in zip(proposed,d['key_id'])]);np.testing.assert_array_equal(expected,d['role'])
    for a,b in [(1,2),(1,3),(2,3)]:
        assert not set(d['group'][expected==a])&set(d['group'][expected==b])
        assert not set(map(tuple,d['incoming'][expected==a]))&set(map(tuple,d['incoming'][expected==b]))
    for code in [1,2,3]:
        m=expected==code;keys,first,gid=np.unique(d['key_id'][m],return_index=True,return_inverse=True)
        np.testing.assert_allclose(np.bincount(gid,weights=d['weight'][m]),1,atol=1e-12)
        role={1:'train',2:'cal',3:'test'}[code];np.testing.assert_array_equal(keys,bootstrap[role+'_key'])
        w=bootstrap[role+'_weights'];comp=d['component'][m][first];reproduced=np.zeros_like(w);rr=np.random.default_rng(2026110387+code)
        for c in sorted(set(comp)):
            ix=np.flatnonzero(comp==c);reproduced[:,ix]=rr.multinomial(len(ix),np.ones(len(ix))/len(ix),size=500)
        np.testing.assert_array_equal(w,reproduced)
    e,z,f=d['truth_E_GeV'],d['pz'],d['y_lepton'];valid=d['label_physical']
    masks=dict(all=np.ones(len(e),bool),E50_100=(50<=e)&(e<100),E100_200=(100<=e)&(e<200),E200_inf=e>=200,
       pz50_100=z<100,pz50_100_trueE200=(z<100)&(e>=200),high_y=valid&(f>=.8),unconfirmed=~d['confirmed'],
       confirmed_low_transfer=valid&d['confirmed']&(f<.2),input_missing=d['input_missing'],fit_failure=d['fit_failure'],
       response_nominal=~(d['input_missing']|d['wave_invalid']|d['fit_failure']|d['calo_invalid']),negative_valid_raw=d['negative_valid_raw'])
    for lo,hi in [(200,400),(400,800),(800,1600),(1600,3200),(3200,6400)]:masks[f'E{lo}_{hi}']=(e>=lo)&(e<hi)
    masks['E6400_inf']=e>=6400
    prediction=dict(traditional=np.log(z/.8),**{k:v[k] for k in ['direct_raw','direct_cal','bounded_raw','bounded_cal','posterior_raw']})
    for name in ['training','nominal','flat','pressure']:prediction['posterior_'+name]=v['posterior_'+name+'_median']
    rows=list(csv.DictReader((OUT/'metrics.tsv').open(),delimiter='\t'));maxdiff=0.;checked=0
    for row in rows:
        code={'train':1,'cal':2,'test':3}[row['role']];m=(expected==code)&masks[row['stratum']]
        assert m.sum()==int(row['N'])
        if not m.any():continue
        w=d['weight'][m] if row['weighting']=='incoming' else np.ones(m.sum())
        error=prediction[row['policy']][m]-np.log(e[m]);r=np.exp(error)-1
        order=np.argsort(r,kind='stable');weights=w[order];pos=(np.cumsum(weights)-weights/2)/weights.sum();q=np.interp([.16,.5,.84],pos,r[order])
        vals=dict(log_RMSE=np.sqrt(np.dot(w,error**2)/w.sum()),mean_bias_pct=100*np.dot(w,r)/w.sum(),median_bias_pct=100*q[1],R68_pct=50*(q[2]-q[0]),
            tail50_pct=100*np.dot(w,abs(r)>.5)/w.sum(),positive_tail50_pct=100*np.dot(w,r>.5)/w.sum(),negative_tail50_pct=100*np.dot(w,r<-.5)/w.sum())
        for key,val in vals.items():
            diff=abs(val-float(row[key]));assert diff<1e-9,(row['policy'],row['stratum'],key,diff);maxdiff=max(maxdiff,float(diff));checked+=1
    paired=list(csv.DictReader((OUT/'paired.tsv').open(),delimiter='\t'));intervals=0
    for row in paired:
        code={'train':1,'cal':2,'test':3}[row['role']];ids=np.flatnonzero(expected==code)
        keys=bootstrap[row['role']+'_key'];draw=bootstrap[row['role']+'_weights'];m=masks[row['stratum']][ids]
        ix=ids[m];gid=np.searchsorted(keys,d['key_id'][ix]);w=d['weight'][ix];den=draw@np.bincount(gid,weights=w,minlength=len(keys))
        a=prediction[row['candidate']][ix]-np.log(e[ix]);b=prediction[row['reference']][ix]-np.log(e[ix])
        la=draw@np.bincount(gid,weights=w*a*a,minlength=len(keys));lb=draw@np.bincount(gid,weights=w*b*b,minlength=len(keys));good=(den>0)&(lb>0)
        ci=np.quantile(np.sqrt(la[good]/lb[good]),[.025,.975])
        for val,col in zip(ci,['conditional_low95','conditional_high95']):
            diff=abs(val-float(row[col]));assert diff<1e-10;maxdiff=max(maxdiff,float(diff));intervals+=1
        for tail in ['tail50','positive_tail50','negative_tail50']:
            ra,rb=np.expm1(a),np.expm1(b)
            ta=ra>.5 if tail.startswith('positive') else ra<-.5 if tail.startswith('negative') else abs(ra)>.5
            tb=rb>.5 if tail.startswith('positive') else rb<-.5 if tail.startswith('negative') else abs(rb)>.5
            delta=ta.astype(float)-tb.astype(float);bs=(draw@np.bincount(gid,weights=w*delta,minlength=len(keys)))[good]/den[good]*100
            ci=np.percentile(bs,[2.5,97.5])
            for val,col in zip(ci,[tail+'_conditional_low95_pp',tail+'_conditional_high95_pp']):
                diff=abs(val-float(row[col]));assert diff<1e-10;maxdiff=max(maxdiff,float(diff));intervals+=1
    cv=list(csv.DictReader((OUT/'posterior_coverage.tsv').open(),delimiter='\t'));covchecks=0
    for row in cv:
        role=row['role'];code={'cal':2,'test':3}[role];ids=np.flatnonzero(expected==code);mask=masks[row['stratum']][ids];ix=ids[mask]
        prior=row['prior'];lo,hi=('q16','q84') if row['level']=='68' else ('q05','q95');w=d['weight'][ix]
        lower=v[f'posterior_{prior}_{lo}'][ix];upper=v[f'posterior_{prior}_{hi}'][ix];assert (lower<=upper).all()
        covered=(np.log(e[ix])>=lower)&(np.log(e[ix])<=upper);point=100*np.dot(w,covered)/w.sum()
        assert abs(point-float(row['coverage_pct']))<1e-10
        keys=bootstrap[role+'_key'];bw=bootstrap[role+'_weights'];gid=np.searchsorted(keys,d['key_id'][ix]);den=bw@np.bincount(gid,weights=w,minlength=len(keys));good=den>0
        for variable,columns,scale in [(covered,['conditional_low95_pct','conditional_high95_pct'],100),
             (v[f'posterior_{prior}_pit'][ix],['mean_PIT_conditional_low95','mean_PIT_conditional_high95'],1)]:
            vals=(bw@np.bincount(gid,weights=w*variable,minlength=len(keys)))[good]/den[good]*scale;ci=np.percentile(vals,[2.5,97.5])
            for val,col in zip(ci,columns):
                diff=abs(val-float(row[col]));assert diff<1e-10;maxdiff=max(maxdiff,float(diff));covchecks+=1
    md=json.loads((OUT/'fit.json').read_text());assert md['formal_energy_models']==5 and len(md['records'])==5
    for rec in md['records']:assert rec['model_reload_exact']
    save(OUT/'independent_validation.json',dict(passed=True,split_and_native_incoming_disjoint=True,per_key_weight_sum1=True,
        independently_reproduced_all500_draws=True,weighted_metric_values_checked=checked,paired_interval_bounds_checked=intervals,
        posterior_coverage_PIT_interval_bounds_checked=covchecks,max_absolute_difference=maxdiff,formal_models=5,
        source_intervals_certifiable=False,model_reload_exact_all=True,**resources(start)))
    print('Independent split, weights, metrics,500-draw risk and coverage QA passed',flush=True)


if __name__=='__main__':validate()
