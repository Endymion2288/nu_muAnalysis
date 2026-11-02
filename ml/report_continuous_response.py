#!/usr/bin/env python3
"""Fixed point/probability comparisons for stage62; no fitting or model selection."""
import json
import numpy as np

from continuous_response import OUT, ART, MODELS, inputs, begin, resources, save, subset
from expert_combination import REPO, masks, LOW, COST
from report_expert_combination import table, metrics, support, boot_weights


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());d=inputs()
    arrays={}
    for name in MODELS:
        assert json.loads((OUT/name/'fit.json').read_text())['status']=='completed'
        with np.load(ART/name/'predictions.npz') as z:arrays[name]={k:z[k] for k in z.files}
    with np.load(REPO/'ml/artifacts/stage56/predictions.npz') as z:f7={k:z[k] for k in z.files}
    with np.load(REPO/'ml/artifacts/stage60/predictions.npz') as z:old={k:z[k] for k in z.files}
    rows=[];paired=[];probrows=[];probpaired=[];source_rows=[];reliability=[];shape=[];diagnostics=[]
    edges=np.asarray(p['prior_log_edges'])
    thresholds={e:int(np.argmin(abs(edges-np.log(e)))) for e in p['low_probability_thresholds_GeV']}
    for role in ['cal','eval']:
        dd=subset(d,d['role']==role);y=np.log(dd['truth_E_GeV']);mm=masks(dd)
        sample='cal_development' if role=='cal' else 'evaluation'
        for a in arrays.values():np.testing.assert_array_equal(dd['row'],a[role+'_row'])
        np.testing.assert_array_equal(dd['row'],old[role+'_row']);np.testing.assert_array_equal(dd['row'],f7[role+'_row'])
        rawf=f7[role+'_raw_log'].mean(axis=0)
        # Same final F7 offset as stage56; cal is development, never OOF.
        off=float(json.loads((REPO/'workbook/stage60_energy_ml/models.json').read_text())['final']['offset_log'])
        logs=dict(pz0_over0p8=np.log(dd['pz']/.8),F7=rawf+off,
                  stage60=old['cal_final_gate' if role=='cal' else 'eval_gate'])
        for name,a in arrays.items():
            for variant in ['raw','cal']:logs[name+'_'+variant]=a[role+'_point_'+variant+'_log']
            logs[name+'_flat_prior_raw']=a[role+'_flat_point_raw_log']
        groups,gid,w=boot_weights(dd,p['bootstrap_seed']+(role=='cal'),500)

        def mean_ci(values,m):
            point=float(np.mean(values[m])) if m.any() else np.nan
            if len(np.unique(dd['group'][m]))<3:return point,np.nan,np.nan
            den=w@np.bincount(gid[m],minlength=len(groups));good=den>0
            nums=w@np.bincount(gid[m],weights=values[m],minlength=len(groups))
            lo,hi=np.quantile(nums[good]/den[good],[.025,.975])
            return point,float(lo),float(hi)

        for name,pred in logs.items():
            for key,m in mm.items():rows.append(dict(sample=sample,stratum=key,model=name,**support(dd,m),**metrics(y[m],pred[m])))
        for name in ['A_full_unit_raw','A_full_unit_cal']:
            for key,m in mm.items():
                if not m.any():continue
                for ref in ['pz0_over0p8','F7','stage60','B_full_flat_cal','C_mu_unit_cal']:
                    s=(logs[name]-y)**2;r=(logs[ref]-y)**2
                    ratio=float(np.sqrt(s[m].mean()/r[m].mean()))
                    den=w@np.bincount(gid[m],weights=r[m],minlength=len(groups))
                    num=w@np.bincount(gid[m],weights=s[m],minlength=len(groups));good=den>0
                    lo,hi=np.quantile(np.sqrt(num[good]/den[good]),[.025,.975])
                    row=dict(sample=sample,stratum=key,model=name,reference=ref,**support(dd,m),
                        RMSE_ratio=ratio,RMSE_ratio_low95=float(lo),RMSE_ratio_high95=float(hi),
                        gain_pct=100*(1-ratio),gain_low95_pct=100*(1-hi),gain_high95_pct=100*(1-lo))
                    for tail in ['tail50','positive_tail50','negative_tail50','tail100','positive_tail100','negative_tail100']:
                        limit=.5 if '50' in tail else 1.
                        def indicator(pred):
                            v=np.expm1(pred-y)
                            return v>limit if tail.startswith('positive') else v< -limit if tail.startswith('negative') else abs(v)>limit
                        point,low,high=mean_ci(100*(indicator(logs[name]).astype(float)-indicator(logs[ref]).astype(float)),m)
                        row[tail+'_delta_pp']=point;row[tail+'_low95_pp']=low;row[tail+'_high95_pp']=high
                    paired.append(row)
        for name,a in arrays.items():
            for prior in ['unit','flat']:
                prefix=role+('_flat' if prior=='flat' else '')
                logscore=a[prefix+'_log_density'];crps=a[prefix+'_crps_logE']
                probs=a[role+('_flat_probabilities' if prior=='flat' else '_probabilities')]
                for key,m in mm.items():
                    rr=dict(sample=sample,stratum=key,model=name,prior=prior,**support(dd,m),
                        log_density=float(logscore[m].mean()) if m.any() else np.nan,
                        CRPS_logE=float(crps[m].mean()) if m.any() else np.nan,
                        outside_support_N=int(a[role+'_outside_support'][m].sum()))
                    for e,j in thresholds.items():rr['Brier_Elt'+str(e)]=float(np.mean((probs[m,j]-(dd['truth_E_GeV'][m]<e))**2)) if m.any() else np.nan
                    probrows.append(rr)
                for e,j in thresholds.items():
                    pred=probs[:,j];truth=dd['truth_E_GeV']<e
                    for stratum in ['all','pz50_100','high_y','unconfirmed','input_missing']:
                        for low,high in zip(p['reliability_edges'][:-1],p['reliability_edges'][1:]):
                            use=mm[stratum]&(pred>=low)&((pred<high) if high<1 else (pred<=high))
                            reliability.append(dict(sample=sample,stratum=stratum,model=name,prior=prior,threshold_GeV=e,
                                probability_low=low,probability_high=high,**support(dd,use),
                                predicted_probability=float(pred[use].mean()) if use.any() else np.nan,
                                observed_fraction=float(truth[use].mean()) if use.any() else np.nan))
        aa=arrays[MODELS[0]]
        for ref in MODELS[1:]:
            bb=arrays[ref]
            for key,m in mm.items():
                for score,values in [('log_density_gain',aa[role+'_log_density']-bb[role+'_log_density']),
                        ('CRPS_gain',bb[role+'_crps_logE']-aa[role+'_crps_logE'])]:
                    point,lo,hi=mean_ci(values,m)
                    probpaired.append(dict(sample=sample,stratum=key,model=MODELS[0],reference=ref,score=score,
                        **support(dd,m),gain=point,low95=lo,high95=hi))
            pa=aa[role+'_probabilities'];pb=bb[role+'_probabilities']
            tv=.5*np.sum(abs(np.diff(pa,axis=1)-np.diff(pb,axis=1)),axis=1)
            for key,m in mm.items():
                point,lo,hi=mean_ci(tv,m)
                shape.append(dict(sample=sample,stratum=key,comparison='A_vs_'+ref,**support(dd,m),
                    coarse_probability_TV=point,low95=lo,high95=hi,
                    mean_abs_point_log_shift=float(np.mean(abs(aa[role+'_point_raw_log'][m]-bb[role+'_point_raw_log'][m]))) if m.any() else np.nan))
        for name,a in arrays.items():
            tv=.5*np.sum(abs(np.diff(a[role+'_probabilities'],axis=1)-np.diff(a[role+'_flat_probabilities'],axis=1)),axis=1)
            for key,m in mm.items():
                point,lo,hi=mean_ci(tv,m)
                shape.append(dict(sample=sample,stratum=key,comparison=name+'_unit_vs_uniform_inference_prior',**support(dd,m),
                    coarse_probability_TV=point,low95=lo,high95=hi,
                    mean_abs_point_log_shift=float(np.mean(abs(a[role+'_point_raw_log'][m]-a[role+'_flat_point_raw_log'][m]))) if m.any() else np.nan))
                diagnostics.append(dict(sample=sample,stratum=key,model=name,**support(dd,m),
                    normalization_max_error=float(a[role+'_normalization_error'][m].max()) if m.any() else np.nan,
                    mle_boundary_pct=float(100*a[role+'_mle_boundary'][m].mean()) if m.any() else np.nan,
                    multi_interior_peak_pct=float(100*(a[role+'_local_peak_count'][m]>=2).mean()) if m.any() else np.nan,
                    nonunique_near_max_pct=float(100*(a[role+'_mle_high_log'][m]-a[role+'_mle_low_log'][m]>1e-8).mean()) if m.any() else np.nan,
                    outside_support_N=int(a[role+'_outside_support'][m].sum())))
        for group in groups:
            for key in ['all']+LOW+list(COST)[1:]+['input_missing']:
                m=mm[key]&(dd['group']==group)
                if not m.any():continue
                for name,a in arrays.items():
                    source_rows.append(dict(sample=sample,group=group,stratum=key,model=name,**support(dd,m),
                        **metrics(y[m],a[role+'_point_cal_log'][m]),
                        log_density=float(a[role+'_log_density'][m].mean()),CRPS_logE=float(a[role+'_crps_logE'][m].mean())))
    for name,rr in [('metrics',rows),('paired',paired),('probability_metrics',probrows),('probability_paired',probpaired),
            ('source_metrics',source_rows),('reliability',reliability),('shape_sensitivity',shape),('density_diagnostics',diagnostics)]:table(OUT/(name+'.tsv'),rr)
    acceptance=[]
    for variant in ['raw','cal']:
        for key,limit,ref in [(s,1.05,'pz0_over0p8') for s in LOW]+[(s,v,'F7') for s,v in COST.items()]:
            rr=next(r for r in paired if r['sample']=='evaluation' and r['stratum']==key and r['model']=='A_full_unit_'+variant and r['reference']==ref)
            acceptance.append(dict(variant=variant,stratum=key,reference=ref,limit=limit,point_ratio=rr['RMSE_ratio'],upper95=rr['RMSE_ratio_high95'],
                risk_interval_pass=bool(rr['RMSE_ratio_high95']<=limit),tail50_delta_pp=rr['tail50_delta_pp'],tail50_upper95_pp=rr['tail50_high95_pp'],
                tail_interval_pass=bool(rr['tail50_high95_pp']<=2)))
    save(OUT/'acceptance.json',dict(primary_model=MODELS[0],checks=acceptance,
        raw_all_pass=all(r['risk_interval_pass'] and r['tail_interval_pass'] for r in acceptance if r['variant']=='raw'),
        calibrated_all_pass=all(r['risk_interval_pass'] and r['tail_interval_pass'] for r in acceptance if r['variant']=='cal')))
    # Scientific figures from already frozen summaries.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    def figure(fig,name):
        path=OUT/(name+'.svg');fig.savefig(path);fig.savefig(OUT/(name+'.png'),dpi=135);plt.close(fig)
        path.write_text('\n'.join(s.rstrip() for s in path.read_text().splitlines())+'\n')
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    ee=[50,75,100,150,200,400,800,1600,3200,6400]
    for name,label in [('pz0_over0p8','pz0 / 0.8'),('F7','F7'),('stage60','Stage60'),('A_full_unit_cal','A: full unit'),('B_full_flat_cal','B: full flat'),('C_mu_unit_cal','C: mu only')]:
        rr=[next(r for r in rows if r['sample']=='evaluation' and r['model']==name and r['stratum']==f'E{lo}_{hi}') for lo,hi in zip(ee[:-1],ee[1:])]
        for ax,key in zip(axes,['log_RMSE','median_bias_pct']):ax.plot(np.sqrt(np.array(ee[:-1])*ee[1:]),[r[key] for r in rr],'o-',label=label,ms=3)
    for ax in axes:ax.set_xscale('log');ax.set_xlabel('True neutrino energy [GeV]');ax.grid(alpha=.2)
    axes[0].set_ylabel('log-RMSE');axes[1].set_ylabel('Median relative bias [%]');axes[0].legend(fontsize=8)
    fig.suptitle('Fixed smooth ratio models: calibrated point estimates\nDevelopment evaluation, unit MC; probabilities assessed separately')
    figure(fig,'point_response')
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for ax,score in zip(axes,['log_density_gain','CRPS_gain']):
        strata=['all','E50_100','E100_200','pz50_100','high_y','unconfirmed']
        for shift,ref in [(-.08,'C_mu_unit'),(.08,'B_full_flat')]:
            rr=[next(r for r in probpaired if r['sample']=='evaluation' and r['reference']==ref and r['score']==score and r['stratum']==key) for key in strata]
            v=np.array([r['gain'] for r in rr]);low=np.array([r['low95'] for r in rr]);high=np.array([r['high95'] for r in rr])
            # Percentile intervals need not contain the point estimate.
            ax.vlines(np.arange(len(strata))+shift,low,high);ax.plot(np.arange(len(strata))+shift,v,'o',label='A vs '+ref)
        ax.axhline(0,color='black',lw=.7);ax.set_xticks(range(len(strata)),strata,rotation=25);ax.set_ylabel(score+' (positive is better)');ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Raw normalized densities under the same train-frozen prior\n500 source-paired bootstrap draws, fixed models; no response/refit uncertainty')
    figure(fig,'probability_gain')
    fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for ax,e in zip(axes,[100,200]):
        for name in MODELS:
            rr=[r for r in reliability if r['sample']=='evaluation' and r['stratum']=='all' and r['model']==name and r['prior']=='unit' and r['threshold_GeV']==e and r['N']]
            ax.plot([r['predicted_probability'] for r in rr],[r['observed_fraction'] for r in rr],'o-',label=name,ms=4)
        ax.plot([0,1],[0,1],'k--',lw=.7);ax.set_xlabel('Predicted probability');ax.set_ylabel(f'Observed fraction, E < {e} GeV');ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Low-energy reliability: raw densities, no probability calibration')
    figure(fig,'low_energy_reliability')
    curve_sets={name:json.loads((OUT/name/'curves.json').read_text()) for name in MODELS}
    identifiers=[(c['role'],r) for c in curve_sets[MODELS[0]] for r in c['row']]
    fig,axes=plt.subplots(3,4,figsize=(14,9),layout='constrained')
    grid=np.asarray(p['scan_log_grid']);knots=np.unique(np.r_[grid,edges]);h=np.diff(knots)
    pr=np.asarray(p['prior_log_density'])[np.clip(np.searchsorted(edges,.5*(knots[:-1]+knots[1:]))-1,0,len(edges)-2)]
    for ax,(role,row) in zip(axes.flat,identifiers):
        for name in MODELS:
            c=next(c for c in curve_sets[name] if c['role']==role);j=c['row'].index(row)
            logits=np.asarray(c['logits'][j]);v=np.interp(knots,grid,np.exp(logits-logits.max()))
            left,right=v[:-1]*pr,v[1:]*pr;z=np.sum(.5*(left+right)*h)
            ax.plot(np.exp(np.column_stack([knots[:-1],knots[1:]]).ravel()),np.column_stack([left,right]).ravel()/z,label=name,lw=1)
        ax.axvline(c['truth_E_GeV'][j],color='black',ls='--',lw=.7)
        ax.set_xscale('log');ax.set_title(f"{role} row {row}, pz={c['pz_GeV'][j]:.1f} GeV",fontsize=8);ax.grid(alpha=.2)
        ax.set_xlabel('Hypothetical energy [GeV]');ax.set_ylabel('Density per unit logE')
    axes.flat[0].legend(fontsize=7)
    for ax in list(axes.flat)[len(identifiers):]:ax.set_visible(False)
    fig.suptitle('Normalized conditional distributions: train/cal rows fixed before fitting\nDashed line is truth for diagnosis; no evaluation examples selected')
    figure(fig,'conditional_curves')
    save(OUT/'report_resources.json',dict(**resources(start),additional_fits=0,bootstrap_replicates=500,
        interval_scope='fixed predictions, component-stratified source paired; exclude refit/calibration/response/research selection; no multiplicity correction'))
    print(json.dumps(json.loads((OUT/'acceptance.json').read_text()),indent=2))


if __name__=='__main__':main()
