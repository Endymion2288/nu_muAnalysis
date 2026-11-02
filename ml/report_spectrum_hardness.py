#!/usr/bin/env python3
"""Independent event-level checks and compact stage65 figures; no new fit."""
import csv
import json
import time
import numpy as np
from spectrum_hardness import OUT, REPO, begin, resources
from joint_response import information


def main():
    start=begin();tick=time.perf_counter()
    p=json.loads((OUT/'protocol.json').read_text())
    summary=json.loads((OUT/'summary.json').read_text())
    models=json.loads((OUT/'models.json').read_text())
    with np.load(REPO/p['input_cache']) as z:d={k:z[k] for k in z.files}
    prior=json.loads((REPO/'workbook/stage63_energy_ml/protocol_v2.json').read_text())
    for rep,value,edge in [('M_mu','M','M_edges'),('S_scalar','S','S_edges')]:
        index=np.searchsorted(prior['binning'][edge],d[value],side='right')
        index[~np.isfinite(d[value])]=16
        np.testing.assert_array_equal(index,d[rep])
    protected=[]
    assert np.all(d['pz']>50)
    for row in summary['protected_counts']:
        take=d['role']==row['role']
        measured=dict(role=row['role'],N=int(take.sum()),sources=len(np.unique(d['group'][take])),
            low_N=int(d['low'][take].sum()),missing_inputs_N=int(d['missing'][take].sum()),
            unconfirmed_N=int((~d['confirmed'][take]).sum()),
            negative_correction_N=int((d['S'][take]<d['M'][take]).sum()))
        assert measured==row
        protected.append(dict(**measured,high_y_N=int((d['y_lepton'][take]>=.8).sum()),
            reco_pz50_100_N=int((d['pz'][take]<100).sum())))
    boot=np.load(OUT/'bootstrap.npz')
    worst={k:0. for k in ['derivative','direction','inverse_covariance','operator',
        'Fisher','sigma','bootstrap_Fisher','bootstrap_projection','residual']}
    def check(key,a,b,tol=1e-8):
        delta=float(np.max(abs(np.asarray(a)-np.asarray(b))))
        worst[key]=max(worst[key],delta)
        np.testing.assert_allclose(a,b,rtol=tol,atol=tol)
    # Independently recover event multiplicities for predeclared bootstrap indices.
    draws={}
    for role in ['train','cal','eval']:
        take=d['role']==role;groups=np.unique(d['group'][take]);rng=np.random.default_rng(p['bootstrap_seeds'][role])
        matrix=np.zeros((500,len(groups)),int)
        for component in ['pi','k','charm']:
            idx=[i for i,g in enumerate(groups) if str(g).split(':')[0]==component]
            if idx:matrix[:,idx]=rng.multinomial(len(idx),[1/len(idx)]*len(idx),size=500)
        draws[role]=[matrix[j,np.searchsorted(groups,d['group'][take])] for j in [0,249,499]]
    def counts(role,rep,weights=None):
        mask=d['role']==role;low=d['low'][mask];E=d['truth_E_GeV'][mask];z=d[rep][mask]
        w=np.ones(mask.sum()) if weights is None else weights
        k=np.searchsorted(p['truth_E_edges_GeV'],E,side='right')*3+np.array([p['production_components'].index(str(c)) for c in d['component'][mask]])
        out=np.zeros((2,(len(p['truth_E_edges_GeV'])+1)*3,p['category_counts'][rep]))
        np.add.at(out,((~low).astype(int),k,z),w)
        h=np.bincount(z[~low],weights=w[~low]*np.log(E[~low]/400),minlength=out.shape[-1])
        return out,h
    def calculate(t,h,f,finite):
        mc=t.sum(axis=1);n=mc.sum(axis=1);a,b=mc/n[:,None]
        C=(h-mc[1]*h.sum()/n[1])/n[1];D=np.array([a-b,(1-f)*C]).T
        q=f*a+(1-f)*b
        V=(np.diag(q)-np.outer(q,q))/1000
        if finite:V+=f*f*(np.diag(a)-np.outer(a,a))/n[0]+(1-f)**2*(np.diag(b)-np.outer(b,b))/n[1]
        # Work in a reduced sum-zero basis on occupied bins (independent inverse).
        use=np.flatnonzero(q>0);m=len(use)
        contrast=np.vstack([np.eye(m-1),-np.ones(m-1)])
        Q=np.linalg.qr(contrast)[0];reduced=Q.T@V[np.ix_(use,use)]@Q
        W=np.zeros_like(V);W[np.ix_(use,use)]=Q@np.linalg.inv(reduced)@Q.T
        I=D.T@W@D;inverse=np.linalg.inv(I);op=np.linalg.solve(I,D.T@W);fixed=D[:,0]@W/I[0,0]
        sigma=np.sqrt(np.diag(inverse));corr=-I[0,1]/np.sqrt(I[0,0]*I[1,1])
        rho=abs(corr);condition=(1+rho)/(1-rho)
        vals=[1/np.sqrt(I[0,0]),sigma[0],sigma[1],corr,sigma[0]*np.sqrt(I[0,0]),condition,2.,C.sum(),np.max(abs(op@D-np.eye(2)))]
        return D,W,I,fixed,op,np.array(vals)
    def vectors(t,r,f):
        v=np.zeros((3,4,t.shape[-1]))
        for c,fc in enumerate([f,1-f]):
            nt=t[c].sum();nr=r[c].sum()
            for k in range(t.shape[1]):
                x=t[c,k];y=r[c,k];xt=x.sum();yt=y.sum()
                if xt>0 and yt>0:
                    v[c,0]+=fc*(yt/nr-xt/nt)*x/xt
                    v[c,1]+=fc*yt/nr*(y/yt-x/xt)
                else:v[c,2]+=fc*(y/nr-x/nt)
            v[c,3]=fc*(r[c].sum(axis=0)/nr-t[c].sum(axis=0)/nt)
        v[2]=v[0]+v[1];return v
    def projection(v,D,W,o1,o2):
        fixed=v@o1;free=v@o2.T
        rf=v-fixed[...,None]*D[:,0];ru=v-free@D.T
        values=np.stack([fixed,free[...,0],free[...,1],abs(rf).sum(axis=-1)/2,abs(ru).sum(axis=-1)/2,
            np.sqrt(np.maximum(np.einsum('...i,ij,...j->...',rf,W,rf),0)),
            np.sqrt(np.maximum(np.einsum('...i,ij,...j->...',ru,W,ru),0))],axis=-1)
        return values,rf,ru
    checked=0
    residual_table=list(csv.DictReader((OUT/'residuals.csv').open()))
    for row,model in zip(summary['Fisher'],models):
        point=row['point'];rep=row['representation'];finite=row['finite_MC'];f=row['f']
        t,h=counts('train',rep);D,W,I,o1,o2,values=calculate(t,h,f,finite)
        check('direction',D,model['D']);check('inverse_covariance',W,model['inverse_covariance'])
        check('Fisher',I,row['fisher']);check('operator',o2,model['free_operator'])
        check('sigma',values[:3],[row['sigma_f_fixed'],row['sigma_f_free'],row['sigma_alpha']])
        check('sigma',row['sigma_f_fixed'],information(t.sum(axis=1),f,1000,finite))
        check('sigma',row['Schur_sigma_f'],row['sigma_f_free'])
        # Actual-event finite difference is numerical derivative QA only.
        high=(d['role']=='train')&(~d['low']);u=np.log(d['truth_E_GeV'][high]/400);bins=d[rep][high];step=p['derivative_difference_step']
        def tilt(alpha):
            weights=np.exp(alpha*u);return np.bincount(bins,weights=weights,minlength=D.shape[0])/weights.sum()
        check('derivative',(tilt(step)-tilt(-step))/(2*step),D[:,1]/(1-f),tol=1e-8)
        key=f'{point}_{rep}_{"finite" if finite else "known"}'
        if point!='reference':
            r,_=counts(point,rep);v=vectors(t,r,f);_,rf,ru=projection(v,D,W,o1,o2)
            for mode,arr in [('fixed',rf),('free',ru)]:
                rows=[x for x in residual_table if x['point']==point and x['representation']==rep and x['finite_MC']==str(finite) and x['mode']==mode]
                check('residual',arr.reshape(-1),[float(x['delta_probability']) for x in rows])
        for j,b in enumerate([0,249,499]):
            bt,bh=counts('train',rep,draws['train'][j]);bD,bW,bI,bo1,bo2,bv=calculate(bt,bh,f,finite)
            check('bootstrap_Fisher',bv,boot[key+'_Fisher'][b])
            if point!='reference':
                br,_=counts(point,rep,draws[point][j]);v=vectors(bt,br,f)
                result,_,_=projection(v,bD,bW,bo1,bo2)
                check('bootstrap_projection',result,boot[key+'_projection'][b]);checked+=1
    # Fixed-alpha known-response information is independently analytic multinomial.
    for rep in ['M_mu','S_scalar']:
        row=next(r for r in summary['Fisher'] if r['point']=='reference' and r['representation']==rep and not r['finite_MC'])
        t,_=counts('train',rep);mc=t.sum(axis=1);a,b=mc/mc.sum(axis=1)[:,None];q=row['f']*a+(1-row['f'])*b;mask=q>0
        check('sigma',row['sigma_f_fixed'],1/np.sqrt(1000*np.sum((a[mask]-b[mask])**2/q[mask])))
    invalid={k:int((~np.isfinite(boot[k])).sum()) for k in boot.files}
    assert all(n==0 for n in invalid.values())
    qa=dict(passed=True,independent_method='direct weighted event accumulation, reduced simplex covariance inverse, direct stratum decomposition',
        central_models_checked=12,bootstrap_indices=[0,249,499],bootstrap_projection_cases=checked,
        maximum_absolute_differences=worst,invalid_array_entries=invalid,
        binning_and_protection_checks_pass=True,protected_counts=protected,wall_s=time.perf_counter()-tick)
    (OUT/'verification.json').write_text(json.dumps(qa,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,3.5))
    for rep,color in [('M_mu','tab:blue'),('S_scalar','tab:orange')]:
        rows=[r for r in summary['Fisher'] if r['representation']==rep and r['finite_MC']]
        x=np.arange(3);label=rep.split('_')[0]
        axes[0].plot(x,[100*r['sigma_r_over_r_fixed'] for r in rows],'o--',color=color,label=label+' fixed')
        axes[0].plot(x,[100*r['sigma_r_over_r_free'] for r in rows],'s-',color=color,label=label+' free')
        axes[1].plot(x,[r['parameter_correlation'] for r in rows],'o-',color=color,label=label)
        axes[2].plot(x,[r['sigma_f_cost_ratio'] for r in rows],'o-',color=color,label=label)
    for ax in axes:ax.set_xticks(range(3),['reference','cal','eval']);ax.grid(alpha=.25)
    axes[0].set_ylabel(r'Local $\sigma_r/r$ [%]');axes[0].legend(fontsize=8)
    axes[1].set_ylabel(r'Correlation $(f,\alpha)$');axes[2].set_ylabel('Free / fixed uncertainty')
    fig.suptitle(r'Selected N=1000; local $\alpha=0$; finite template MC')
    fig.tight_layout();fig.savefig(OUT/'local_information.png',dpi=140);plt.close(fig)
    rows=list(csv.DictReader((OUT/'projections.csv').open()))
    def get(point,rep,term,quantity):
        return next(x for x in rows if x['point']==point and x['representation']==rep and x['finite_MC']=='True' and x['component']=='combined' and x['term']==term and x['quantity']==quantity)
    fig,axes=plt.subplots(1,3,figsize=(12,3.5));labels=[]
    for i,(point,rep) in enumerate([(a,b) for a in ['cal','eval'] for b in ['M_mu','S_scalar']]):
        labels.append(point+' '+rep[0])
        for mode,dx,color in [('fixed',-.12,'tab:blue'),('free',.12,'tab:orange')]:
            for ax,quantity,scale in [(axes[0],mode+'_delta_f',100),(axes[2],mode+'_weighted_norm',1)]:
                r=get(point,rep,'total',quantity);v,lo,hi=[float(r[k])*scale for k in ['central','low95','high95']]
                ax.errorbar(i+dx,v,yerr=[[max(0,v-lo)],[max(0,hi-v)]],fmt='o',color=color,label=mode if i==0 else None)
        r=get(point,rep,'total','free_delta_alpha');v,lo,hi=[float(r[k]) for k in ['central','low95','high95']]
        axes[1].errorbar(i,v,yerr=[[max(0,v-lo)],[max(0,hi-v)]],fmt='o',color='tab:orange')
    for ax in axes:ax.set_xticks(range(4),labels);ax.axhline(0,color='gray',lw=.6);ax.grid(alpha=.25)
    axes[0].set_ylabel(r'Local $\delta f$ [percentage points]');axes[0].legend(fontsize=8)
    axes[1].set_ylabel(r'Local $\delta\alpha$');axes[2].set_ylabel(r'Residual $\sqrt{r^T V^+ r}$')
    fig.suptitle('Total held-out response shift; paired-source 95% intervals')
    fig.tight_layout();fig.savefig(OUT/'response_projections.png',dpi=140);plt.close(fig)
    (OUT/'report_resources.json').write_text(json.dumps(resources(start),indent=2)+'\n')
    print(json.dumps(qa,indent=2))


if __name__=='__main__':main()
