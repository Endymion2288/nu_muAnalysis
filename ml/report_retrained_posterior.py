"""Stage92 complete new/old accurate posterior comparison and independent arithmetic QA."""
import csv
import json

import numpy as np

from support_augmentation import save,table,begin,resources
from report_resplit_energy import strata,metrics,wquantile,incoming_draws
from posterior_numerics import EDGES

TAILS=['tail50','positive_tail50','negative_tail50']


def read(path):
    return list(csv.DictReader(path.open(),delimiter='\t'))


def indicators(error):
    r=np.expm1(error)
    return dict(tail50=abs(r)>.5,positive_tail50=r>.5,negative_tail50=r<-.5)


def report(role,d,v):
    from evaluate_retrained_posterior import OUT,REPO,ROLES
    start=begin();out=OUT/role;y=np.log(d['truth_E_GeV']);w=d['weight'];n=len(w)
    masks=strata(d);masks.update(wave_invalid=d['wave_invalid'],calo_invalid=d['calo_invalid'])
    policies=dict(traditional=np.log(d['pz']/.8),direct_cal=d['direct_cal'],bounded_cal=d['bounded_cal'],posterior_old_accurate=d['old_quantiles'][:,2],posterior_accurate=v['accurate_quantiles'][:,2])
    if not np.isfinite(v['accurate_quantiles']).all() or not np.isfinite(v['accurate_PIT']).all() or not np.isfinite(v['accurate_logscore']).all():
        save(out/'decisions.json',dict(full_risks_measured=False,N=n,noncertified_N=int((~v['numerical_certified']).sum()),
            reason='all rows preserved; unknown numerical values prevent complete-role risks, no valid-only substitution',deployment='retain existing deployment'))
        return
    keys,gid,draw=incoming_draws(d,2026110387+ROLES[role])
    point=[];paired=[];coverage=[];reliability=[];quantile_reliability=[];scores=[];numerical=[]
    oldq=d['old_quantiles']
    distributions=dict(old_accurate=(oldq,d['old_PIT'],d['old_logscore'],d['old_ESS_fraction']),
                       accurate=(v['accurate_quantiles'],v['accurate_PIT'],v['accurate_logscore'],v['accurate_ESS_fraction']))
    old_raw=d['old_training_logscore']
    for layer,mask in masks.items():
        ix=np.flatnonzero(mask);ww=w[ix];N=len(ix)
        support=dict(N=N,unique_incoming=len(np.unique(d['key_id'][ix])),groups=len(np.unique(d['group'][ix])),blocks=len(np.unique(d['block'][ix])),weight_sum=float(ww.sum()))
        for name,p in policies.items():
            for weighting,weight in [('incoming',ww),('record',np.ones(N))]:
                point.append(dict(role=role,stratum=layer,policy=name,weighting=weighting,**support,**metrics(y[ix],p[ix],weight)))
        if not N:continue
        den=draw@np.bincount(gid[ix],weights=ww,minlength=len(keys));good=den>0
        losses={name:draw@np.bincount(gid[ix],weights=ww*(p[ix]-y[ix])**2,minlength=len(keys)) for name,p in policies.items()}
        for reference in ['posterior_old_accurate','direct_cal','bounded_cal','traditional']:
            selected=good&(losses[reference]>0);ratio_draw=np.sqrt(losses['posterior_accurate'][selected]/losses[reference][selected]);ci=np.quantile(ratio_draw,[.025,.975])
            a=policies['posterior_accurate'][ix]-y[ix];b=policies[reference][ix]-y[ix]
            row=dict(role=role,stratum=layer,candidate='posterior_accurate',reference=reference,**support,
                RMSE_ratio=float(np.sqrt(np.dot(ww,a*a)/np.dot(ww,b*b))),conditional_low95=float(ci[0]),conditional_high95=float(ci[1]),valid_draws=int(selected.sum()),
                source_low95='未测量',source_high95='未测量',scope='incoming conditional within component; no source/parent/refit/calibration/response/research-selection uncertainty')
            ta,tb=indicators(a),indicators(b)
            for tail in TAILS:
                difference=ta[tail].astype(float)-tb[tail].astype(float)
                bs=(draw@np.bincount(gid[ix],weights=ww*difference,minlength=len(keys)))[selected]/den[selected]*100
                ci=np.quantile(bs,[.025,.975]);row.update({tail+'_delta_pp':float(100*np.average(difference,weights=ww)),tail+'_conditional_low95_pp':float(ci[0]),tail+'_conditional_high95_pp':float(ci[1])})
            paired.append(row)
        for name,(q,pit,ld,ess) in distributions.items():
            p=pit[ix];mean_draw=(draw@np.bincount(gid[ix],weights=ww*p,minlength=len(keys)))[good]/den[good];pc=np.quantile(mean_draw,[.025,.975])
            for level,lo,hi in [(68,1,3),(90,0,4)]:
                lower=q[ix,lo];upper=q[ix,hi];covered=(y[ix]>=lower)&(y[ix]<=upper)
                bs=(draw@np.bincount(gid[ix],weights=ww*covered,minlength=len(keys)))[good]/den[good];ci=np.quantile(bs,[.025,.975])
                coverage.append(dict(role=role,stratum=layer,method=name,level=level,**support,coverage_pct=float(100*np.average(covered,weights=ww)),
                    conditional_low95_pct=float(100*ci[0]),conditional_high95_pct=float(100*ci[1]),valid_draws=int(good.sum()),
                    mean_PIT=float(np.average(p,weights=ww)),mean_PIT_conditional_low95=float(pc[0]),mean_PIT_conditional_high95=float(pc[1]),
                    median_width_logE=float(wquantile(upper-lower,ww,[.5])[0]),mean_width_logE=float(np.average(upper-lower,weights=ww)),
                    mean_ESS_fraction=float(np.average(ess[ix],weights=ww)),source_interval='未测量'))
            bins=np.minimum((p*10).astype(int),9)
            for j in range(10):reliability.append(dict(role=role,stratum=layer,method=name,PIT_bin=j,weight=float(ww[bins==j].sum()),fraction=float(ww[bins==j].sum()/ww.sum())))
            for j,prob in enumerate([.05,.16,.5,.84,.95]):quantile_reliability.append(dict(role=role,stratum=layer,method=name,probability=prob,N=N,
                empirical_probability=float(np.average(y[ix]<=q[ix,j],weights=ww)),source_interval='未测量',scope='point only'))
            raw=old_raw if name=='old_accurate' else v['accurate_training_logscore']
            scores.append(dict(role=role,stratum=layer,method=name,N=N,nominal_logE_NLL=float(-np.average(ld[ix],weights=ww)),
                training_prior_logE_NLL=float(-np.average(raw[ix],weights=ww)),exact_CRPS='未测量'))
        numerical.append(dict(role=role,stratum=layer,**support,noncertified_N=int((~v['numerical_certified'][ix]).sum()),
            max_abs_median_shift_logE=float(np.max(abs(oldq[ix,2]-v['accurate_quantiles'][ix,2]))),
            max_abs_quantile_shift_logE=float(np.max(abs(oldq[ix]-v['accurate_quantiles'][ix]))),
            max_abs_PIT_shift=float(np.max(abs(d['old_PIT'][ix]-v['accurate_PIT'][ix]))),
            max_abs_logscore_shift=float(np.max(abs(d['old_logscore'][ix]-v['accurate_logscore'][ix])))))
    for name,rows in [('metrics',point),('paired',paired),('coverage',coverage),('PIT_reliability',reliability),('quantile_reliability',quantile_reliability),('scores',scores),('posterior_changes',numerical)]:table(out/(name+'.tsv'),rows)
    decisions=dict(role=role,full_risks_measured=True,N=n,noncertified_N=int((~v['numerical_certified']).sum()),source_intervals_available=False,
        numerical_all_pass=bool(v['numerical_certified'].all()),independent_confirmation=False,new_fits=1,new_calibration=1,point_policy='new originalmodel accurate loss/calibration, fixed nominal prior, adaptive accurate median',deployment='retain existing deployment; development diagnosis only')
    if role=='test':
        gates=[]
        for layer,reference,limit in [('E50_100','traditional',1.05),('E100_200','traditional',1.05)]+[(s,'direct_cal',lim) for s,lim in [('all',1.01),('E200_inf',1.03),('pz50_100',1.03),('pz50_100_trueE200',1.03),('high_y',1.03),('unconfirmed',1.03)]]:
            r=next(v for v in paired if v['stratum']==layer and v['reference']==reference)
            tail=next(v for v in paired if v['stratum']==layer and v['reference']=='direct_cal')
            gates.append(dict(stratum=layer,reference=reference,conditional_RMSE_upper95=r['conditional_high95'],limit=limit,
                conditional_RMSE_pass=bool(r['conditional_high95']<=limit),conditional_tail_pass=bool(all(tail[t+'_conditional_high95_pp']<=2 for t in TAILS)),
                **{t+'_conditional_upper95_pp':tail[t+'_conditional_high95_pp'] for t in TAILS},source_certified=False))
        table(out/'gates.tsv',gates)
        cg=[]
        for r in coverage:
            if r['method']!='accurate' or r['stratum'] not in ['all','E50_100','E100_200','pz50_100_trueE200','high_y','unconfirmed','input_missing']:continue
            cg.append(dict(stratum=r['stratum'],level=r['level'],N=r['N'],sparse=r['N']<20,
                conditional_coverage_pass=bool(r['conditional_low95_pct']>=r['level']-5),
                conditional_mean_PIT_pass=bool(r['mean_PIT_conditional_low95']<=.5<=r['mean_PIT_conditional_high95']),source_certified=False))
        table(out/'coverage_gates.tsv',cg)
        decisions.update(conditional_point_tail_pass=bool(all(r['conditional_RMSE_pass'] and r['conditional_tail_pass'] for r in gates)),
            conditional_coverage_PIT_pass=bool(all(r['conditional_coverage_pass'] and r['conditional_mean_PIT_pass'] and not r['sparse'] for r in cg)))
    if role=='cal':
        original_cal=json.loads((OUT/'posterior_calibration.json').read_text())
        accurate_objective=-float(np.average(v['accurate_training_logscore'],weights=w))
        difference=abs(accurate_objective-original_cal['cal_logE_NLL'])
        save(out/'calibration_objective_closure.json',dict(passed=difference<=1e-6,fullcal_N=n,
            independent_Reference_NLL=accurate_objective,optimizer_NLL=original_cal['cal_logE_NLL'],absolute_difference=difference,tolerance=1e-6))
        decisions['fullcal_objective_closed']=bool(difference<=1e-6)
    save(out/'decisions.json',decisions)
    validate(role,d,v,masks,policies,distributions,keys,gid,draw,old_raw)
    save(out/'report_resources.json',resources(start))
    print(json.dumps(decisions,ensure_ascii=False),flush=True)


def validate(role,d,v,masks,policies,distributions,keys,gid,draw,old_raw):
    from evaluate_retrained_posterior import OUT,REPO,ROLES
    start=begin();out=OUT/role;w=d['weight'];y=np.log(d['truth_E_GeV']);maximum=0.;count=0
    np.testing.assert_allclose(np.bincount(gid,weights=w),1,atol=1e-12)
    # Reproduce every bootstrap multiplicity with separately assembled key/component arrays.
    unique,first,inverse=np.unique(d['key_id'],return_index=True,return_inverse=True)
    np.testing.assert_array_equal(keys,unique);np.testing.assert_array_equal(gid,inverse)
    repeated=np.zeros_like(draw);rng=np.random.default_rng(2026110387+ROLES[role]);component=d['component'][first]
    for c in sorted(set(component)):
        ix=np.flatnonzero(component==c);repeated[:,ix]=rng.multinomial(len(ix),np.ones(len(ix))/len(ix),size=500)
    np.testing.assert_array_equal(draw,repeated)
    def compare(a,b):
        nonlocal maximum,count
        diff=abs(float(a)-float(b));assert diff<1e-9,(a,b,diff);maximum=max(maximum,diff);count+=1
    points=read(out/'metrics.tsv')
    for r in points:
        m=masks[r['stratum']];assert int(r['N'])==int(m.sum())
        if not m.any():continue
        weight=w[m] if r['weighting']=='incoming' else np.ones(m.sum());e=policies[r['policy']][m]-y[m];rel=np.exp(e)-1
        order=np.argsort(rel,kind='stable');ww=weight[order];q=np.interp([.16,.5,.84],(np.cumsum(ww)-ww/2)/ww.sum(),rel[order])
        vals=[np.sqrt(np.dot(weight,e*e)/weight.sum()),q[1]*100,np.dot(weight,rel)/weight.sum()*100,(q[2]-q[0])*50,
              np.dot(weight,abs(rel)>.5)/weight.sum()*100,np.dot(weight,rel>.5)/weight.sum()*100,np.dot(weight,rel<-.5)/weight.sum()*100]
        for key,x in zip(['log_RMSE','median_bias_pct','mean_bias_pct','R68_pct','tail50_pct','positive_tail50_pct','negative_tail50_pct'],vals):compare(r[key],x)
    for r in read(out/'paired.tsv'):
        m=masks[r['stratum']];ix=np.flatnonzero(m);ww=w[ix]
        den=draw@np.bincount(gid[ix],weights=ww,minlength=len(keys));a=policies['posterior_accurate'][ix]-y[ix];b=policies[r['reference']][ix]-y[ix]
        la=draw@np.bincount(gid[ix],weights=ww*a*a,minlength=len(keys));lb=draw@np.bincount(gid[ix],weights=ww*b*b,minlength=len(keys));good=(den>0)&(lb>0)
        ci=np.percentile(np.sqrt(la[good]/lb[good]),[2.5,97.5]);compare(r['conditional_low95'],ci[0]);compare(r['conditional_high95'],ci[1])
        ra,rb=np.expm1(a),np.expm1(b)
        for tail in TAILS:
            aa=ra>.5 if tail.startswith('positive') else ra<-.5 if tail.startswith('negative') else abs(ra)>.5
            bb=rb>.5 if tail.startswith('positive') else rb<-.5 if tail.startswith('negative') else abs(rb)>.5
            bs=(draw@np.bincount(gid[ix],weights=ww*(aa.astype(float)-bb.astype(float)),minlength=len(keys)))[good]/den[good]*100
            ci=np.percentile(bs,[2.5,97.5]);compare(r[tail+'_conditional_low95_pp'],ci[0]);compare(r[tail+'_conditional_high95_pp'],ci[1])
    for r in read(out/'coverage.tsv'):
        ix=np.flatnonzero(masks[r['stratum']]);ww=w[ix];q,pit,_,_=distributions[r['method']];lo,hi=(1,3) if r['level']=='68' else (0,4)
        cover=(y[ix]>=q[ix,lo])&(y[ix]<=q[ix,hi]);den=draw@np.bincount(gid[ix],weights=ww,minlength=len(keys));good=den>0
        compare(r['coverage_pct'],np.dot(ww,cover)/ww.sum()*100)
        for variable,cols,scale in [(cover,['conditional_low95_pct','conditional_high95_pct'],100),(pit[ix],['mean_PIT_conditional_low95','mean_PIT_conditional_high95'],1)]:
            bs=(draw@np.bincount(gid[ix],weights=ww*variable,minlength=len(keys)))[good]/den[good]*scale;ci=np.percentile(bs,[2.5,97.5])
            compare(r[cols[0]],ci[0]);compare(r[cols[1]],ci[1])
    for r in read(out/'scores.tsv'):
        ix=np.flatnonzero(masks[r['stratum']]);ww=w[ix]
        raw=old_raw if r['method']=='old_accurate' else v['accurate_training_logscore']
        compare(r['nominal_logE_NLL'],-np.dot(ww,distributions[r['method']][2][ix])/ww.sum())
        compare(r['training_prior_logE_NLL'],-np.dot(ww,raw[ix])/ww.sum())
    # Exact old baseline arithmetic, without recomputing baseline predictions.
    old=read(REPO/'workbook/stage87_energy_ml/metrics.tsv');baseline=0
    for r in points:
        if r['policy'] not in ['traditional','direct_cal','bounded_cal'] or r['N']=='0':continue
        match=[a for a in old if a['role']==role and a['stratum']==r['stratum'] and a['policy']==r['policy'] and a['weighting']==r['weighting']]
        if not match:continue
        for key in ['log_RMSE','median_bias_pct','mean_bias_pct','R68_pct','tail50_pct','positive_tail50_pct','negative_tail50_pct']:compare(r[key],match[0][key]);baseline+=1
    old=read(REPO/f'workbook/stage89_energy_ml/{role}/metrics.tsv')
    for r in points:
        if r['policy']!='posterior_old_accurate' or r['N']=='0':continue
        match=[a for a in old if a['stratum']==r['stratum'] and a['policy']=='posterior_accurate' and a['weighting']==r['weighting']]
        if not match:continue
        for key in ['log_RMSE','median_bias_pct','mean_bias_pct','R68_pct','tail50_pct','positive_tail50_pct','negative_tail50_pct']:compare(r[key],match[0][key]);baseline+=1
    save(out/'independent_validation.json',dict(passed=True,identity_N=len(w),per_key_total_weight1=True,all500_draws_reproduced=True,checked_numeric_values=count,
        stage87_baseline_values_reproduced=baseline,max_absolute_difference=maximum,source_intervals_certified=False,
        numerical_certified_N=int(v['numerical_certified'].sum()),new_fits=1,**resources(start)))
