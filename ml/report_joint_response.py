#!/usr/bin/env python3
"""Independent count/convex checks and compact stage63 tables/figures."""
import csv
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize

from joint_response import OUT,ART,REPRESENTATIONS,assign,histogram,begin,resources,save


def table(name,rows):
    with (OUT/name).open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)


def independent_profile(mc,data,f):
    """Direct convex SLSQP, no EM, independent optimizer initialisation."""
    use=(mc.sum(axis=0)+data)>0;mc=mc[:,use];data=data[use];k=len(data)
    total=mc.sum(axis=1);scale=mc.sum()+data.sum()
    def fun(x):
        a,b=x[:k],x[k:];q=f*a+(1-f)*b
        terms=[(data,q),(mc[0],a),(mc[1],b)];value=0.
        for counts,prob in terms:
            nz=counts>0
            if np.any(prob[nz]<=0):return 1e100,np.zeros(2*k)
            value+=np.sum(counts[nz]*np.log(counts[nz]/counts.sum()/prob[nz]))
        g=data/np.maximum(q,1e-300)
        grad=np.r_[-mc[0]/np.maximum(a,1e-300)-f*g,-mc[1]/np.maximum(b,1e-300)-(1-f)*g]
        return value/scale,grad/scale
    jac=np.zeros((2,2*k));jac[0,:k]=1;jac[1,k:]=1
    initial=(mc+1)/(total[:,None]+k)
    result=minimize(fun,initial.ravel(),jac=True,method='SLSQP',bounds=[(1e-14,1)]*(2*k),
        constraints=[dict(type='eq',fun=lambda x:jac@x-1,jac=lambda x:jac)],
        options={'ftol':1e-14,'maxiter':500})
    assert result.success,result.message
    return float(result.fun*scale)


def main():
    start=begin();p=json.loads((OUT/'protocol_v2.json').read_text());fits=json.loads((OUT/'fits.json').read_text())
    summary=json.loads((OUT/'summary.json').read_text());support=json.loads((OUT/'support.json').read_text())
    corrections=[]
    for r in fits:
        if not 0<r['f_true']<1:
            keys=['relative_sigma_r','sigma_r','bias_f_sigma','bias_r_sigma']
            corrections.append(dict(role=r['role'],source=r['source'],representation=r['representation'],finite_MC=r['finite_MC'],
                original_diagnostics={k:r[k] for k in keys},reason='true component fraction at physical boundary: no regular pull/relative-r interpretation'))
            for k in keys:r[k]=None
    if not (OUT/'boundary_reporting.json').exists():save(OUT/'boundary_reporting.json',corrections)
    save(OUT/'fits.json',fits)
    with np.load(ART/'observables.npz') as z:d={k:z[k] for k in z.files}
    train=d['role']=='train';bins=assign(d['M'],d['S'],p)
    for name in REPRESENTATIONS:np.testing.assert_array_equal(bins[name],d[name])
    templates={name:histogram(d[name][train],d['low'][train],np.ones(train.sum()),p['category_counts'][name]) for name in REPRESENTATIONS}
    assert len(fits)==294 and summary['exact_profile_fits']==294
    for r in fits:
        np.testing.assert_allclose(sum(r['data_counts']),1000,atol=1e-10,rtol=0)
        assert r['grid_global_check_pass'] and r['max_simplex_KKT']<p['EM_KKT_tolerance']
    comparisons=[]
    for r in fits:
        if not r['finite_MC'] or r['source'] not in ['reference','pooled'] or r['variant']!='nominal':continue
        for label,f,expected in [('minimum',r['f_hat'],r['twice_NLL_min']/2),
                                 ('low68',r['f_low68'],r['twice_NLL_min']/2+.5),
                                 ('high68',r['f_high68'],r['twice_NLL_min']/2+.5)]:
            if f in [0,1]:continue
            value=independent_profile(templates[r['representation']],np.array(r['data_counts']),f)
            error=abs(value-expected);assert error<2e-6,(r['role'],r['representation'],label,error)
            comparisons.append(dict(role=r['role'],representation=r['representation'],point=label,NLL_error=error))
    fields=['role','source','variant','representation','finite_MC','case_N','weighted_ESS','f_true','f_hat','f_low68','f_high68',
        'r_true','r_hat','r_low68','r_high68','sigma_f','sigma_r','relative_sigma_r','bias_f_sigma','bias_r_sigma',
        'truth_in_profile68','boundary','interval_hits_boundary','twice_NLL_min','max_simplex_KKT','convex_polish_calls','wall_s']
    rows=[{k:r[k] for k in fields} for r in fits]
    table('all_fits.csv',rows);table('pooled_fits.csv',[r for r in rows if r['source']=='pooled'])
    table('source_fits.csv',[r for r in rows if r['source'] not in ['reference','pooled']])
    table('support.csv',support);table('templates.csv',json.loads((OUT/'templates.json').read_text()))
    source_summary=[]
    for role in ['cal','eval']:
        for name in REPRESENTATIONS:
            rr=[r for r in fits if r['role']==role and r['source']!='pooled' and r['finite_MC'] and r['representation']==name]
            pulls=[abs(r['bias_r_sigma']) for r in rr if r['bias_r_sigma'] is not None]
            source_summary.append(dict(role=role,representation=name,sources=len(rr),regular=len(pulls),
                zero_low_sources=sum(r['f_true']==0 for r in rr),boundary_fits=sum(r['boundary'] for r in rr),
                abs_bias_r_sigma_median=float(np.median(pulls)),abs_bias_r_sigma_max=float(max(pulls)),
                truth_in_profile68_sources=sum(r['truth_in_profile68'] for r in rr)))
    table('source_summary.csv',source_summary)
    response_rows=[]
    for role in ['train','cal','eval']:
        for low in [True,False]:
            take=(d['role']==role)&(d['low']==low)
            for name in REPRESENTATIONS:
                h=np.bincount(d[name][take],minlength=p['category_counts'][name]);prob=h/h.sum()
                reference=templates[name][0 if low else 1];reference=reference/reference.sum()
                response_rows.append(dict(role=role,component='true50_200' if low else 'true200_inf',representation=name,
                    N=int(take.sum()),sources=len(np.unique(d['group'][take])),zero_cells=int((h==0).sum()),
                    TV_to_train=float(.5*abs(prob-reference).sum()),mean_M=float(d['M'][take].mean()),
                    mean_S=float(d['S'][take].mean()),mean_log_truth_E=float(np.log(d['truth_E_GeV'][take]).mean())))
    table('component_response.csv',response_rows)
    layers=np.searchsorted(p['binning']['J_M_edges'],d['M'],side='right');layer_rows=[]
    for role in ['train','cal','eval']:
        for layer in range(len(p['binning']['J_M_edges'])+1):
            take=(d['role']==role)&(layers==layer)
            layer_rows.append(dict(role=role,M_layer=layer,N=int(take.sum()),low_N=int((take&d['low']).sum()),
                high_N=int((take&~d['low']).sum())))
    table('joint_layer_support.csv',layer_rows)
    # Curvature and closure diagnostics; neither plot asserts toy coverage.
    colors=['#666666','#2878b5','#c94732'];fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for j,name in enumerate(REPRESENTATIONS):
        ref=[r for r in summary['reference_Fisher'] if r['representation']==name]
        axes[0].plot([0,1],[100*r['relative_sigma_r'] for r in ref],'-o',color=colors[j],label=name)
    axes[0].set(xticks=[0,1],xticklabels=['Known response','Finite MC'],ylabel=r'$\sigma(r)/r$ [%]',title='Train reference; selected N = 1000')
    axes[0].legend(frameon=False)
    labels=['nominal','low_internal_0.75','low_internal_1.25','high_y_mix_0.75','high_y_mix_1.25']
    for j,name in enumerate(REPRESENTATIONS):
        for role,style in [('cal','--'),('eval','-')]:
            rr=[next(r for r in fits if r['role']==role and r['source']=='pooled' and r['variant']==v and r['finite_MC'] and r['representation']==name) for v in labels]
            axes[1].plot(np.arange(5),[r['bias_r_sigma'] for r in rr],style+'o',color=colors[j],label=f'{role} {name}',markersize=4)
    axes[1].axhspan(-1,1,color='gray',alpha=.12);axes[1].axhline(0,color='black',lw=.6)
    axes[1].set(xticks=np.arange(5),xticklabels=['Nominal','Low .75','Low 1.25','High-y .75','High-y 1.25'],
        ylabel=r'$(\hat r-r_{true})/\sigma_r$',title='Source holdout closure and shape stress')
    axes[1].tick_params(axis='x',rotation=25);axes[1].legend(frameon=False,fontsize=7,ncol=2)
    fig.savefig(OUT/'joint_response.png',dpi=160);fig.savefig(OUT/'joint_response.pdf');plt.close(fig)
    save(OUT/'validation.json',dict(independent_convex_profiles=comparisons,
        largest_independent_NLL_error=max(r['NLL_error'] for r in comparisons),
        counts_binning_and_all_294_checks_pass=True,positive_MC_probability_analytic_lower_bound=float(1/(templates['M_mu'].sum(axis=1).max()+1000)),
        numerical_floor=1e-14,numerical_floor_inactive_for_positive_MC_cells=True,
        source_summary=source_summary,component_response=response_rows,
        selected_pz_range_GeV=[float(d['pz'].min()),float(d['pz'].max())],
        selected_truth_E_range_GeV=[float(d['truth_E_GeV'].min()),float(d['truth_E_GeV'].max())],resources=resources(start)))
    print(json.dumps(dict(summary=summary,source_summary=source_summary),indent=2))


if __name__=='__main__':main()
