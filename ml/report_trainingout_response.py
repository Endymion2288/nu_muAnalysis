#!/usr/bin/env python3
"""Independent event/simplex QA and train-vs-cal template comparison, no fits."""
import csv
import json
import numpy as np
from trainingout_response import OUT,REPO,REPRESENTATIONS,TERMS,COMPONENTS,table,begin,resources,save
from joint_response import information


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());f=p['f_eval']
    summary=json.loads((OUT/'summary.json').read_text());models=json.loads((OUT/'models.json').read_text())
    with np.load(REPO/p['input_cache']) as z:d={k:z[k] for k in z.files}
    boot=np.load(OUT/'bootstrap.npz');prior=REPO/'workbook/stage65_energy_ml'
    original=json.loads((REPO/'workbook/stage63_energy_ml/protocol_v2.json').read_text())
    previous_protection=json.loads((prior/'verification.json').read_text())['protected_counts']
    for rep,value,edge in [('M_mu','M','M_edges'),('S_scalar','S','S_edges')]:
        ix=np.searchsorted(original['binning'][edge],d[value],side='right');ix[~np.isfinite(d[value])]=16
        np.testing.assert_array_equal(ix,d[rep])
    assert np.all(d['pz']>50)
    protected=[]
    for row in summary['protected_counts']:
        take=d['role']==row['role']
        measured=dict(role=row['role'],N=int(take.sum()),sources=len(np.unique(d['group'][take])),low_N=int(d['low'][take].sum()),
            missing_inputs_N=int(d['missing'][take].sum()),unconfirmed_N=int((~d['confirmed'][take]).sum()),
            negative_correction_N=int((d['S'][take]<d['M'][take]).sum()))
        assert measured==row
        measured.update(high_y_N=int((d['y_lepton'][take]>=.8).sum()),reco_pz50_100_N=int((d['pz'][take]<100).sum()))
        assert measured==next(r for r in previous_protection if r['role']==row['role']);protected.append(measured)
    errors={key:0. for key in ['derivative','direction','covariance_inverse','Fisher','operator','sigma','vectors','residuals','bootstrap_Fisher','bootstrap_projection','ESS']}
    def check(key,a,b,tol=1e-8):
        errors[key]=max(errors[key],float(np.max(abs(np.asarray(a)-np.asarray(b)))))
        np.testing.assert_allclose(a,b,rtol=tol,atol=tol)
    def read(path):return list(csv.DictReader(path.open()))
    def event_counts(role,rep,weights=None):
        take=d['role']==role;E=d['truth_E_GeV'][take];z=d[rep][take];low=d['low'][take]
        k=np.searchsorted(p['truth_E_edges_GeV'],E,side='right')*3+np.array([p['production_components'].index(str(c)) for c in d['component'][take]])
        w=np.ones(take.sum()) if weights is None else weights
        h=np.zeros((2,27,17));np.add.at(h,((~low).astype(int),k,z),w)
        moment=np.bincount(z[~low],weights=w[~low]*np.log(E[~low]/400),minlength=17)
        return h,moment,k
    def solve(t,h,finite):
        mc=t.sum(axis=1);n=mc.sum(axis=1);a,b=mc/n[:,None]
        C=h/n[1]-b*h.sum()/n[1];D=np.array([a-b,(1-f)*C]).T;q=f*a+(1-f)*b
        V=(np.diag(q)-np.outer(q,q))/1000
        if finite:V+=f*f*(np.diag(a)-np.outer(a,a))/n[0]+(1-f)**2*(np.diag(b)-np.outer(b,b))/n[1]
        occupied=np.flatnonzero(q>0);m=len(occupied)
        Q=np.linalg.qr(np.vstack([np.eye(m-1),-np.ones(m-1)]))[0]
        W=np.zeros_like(V);W[np.ix_(occupied,occupied)]=Q@np.linalg.inv(Q.T@V[np.ix_(occupied,occupied)]@Q)@Q.T
        I=D.T@W@D;inverse=np.linalg.inv(I);op=np.linalg.solve(I,D.T@W);fixed=D[:,0]@W/I[0,0]
        sigma=np.sqrt(np.diag(inverse));rho=-I[0,1]/np.sqrt(I[0,0]*I[1,1])
        values=[1/np.sqrt(I[0,0]),sigma[0],sigma[1],rho,sigma[0]*np.sqrt(I[0,0]),(1+abs(rho))/(1-abs(rho)),2.,C.sum(),np.max(abs(op@D-np.eye(2)))]
        return D,W,I,fixed,op,values
    def direct_vectors(t,r):
        raw=np.zeros((2,4,17));unmatched=np.zeros((2,2))
        for c in range(2):
            nt=t[c].sum();nr=r[c].sum()
            for k in range(27):
                x=t[c,k];y=r[c,k];xt=x.sum();yt=y.sum()
                if xt>0 and yt>0:
                    raw[c,0]+=(yt/nr-xt/nt)*x/xt;raw[c,1]+=yt/nr*(y/yt-x/xt)
                else:
                    raw[c,2]+=y/nr-x/nt;unmatched[c]+=[xt/nt,yt/nr]
            raw[c,3]=r[c].sum(axis=0)/nr-t[c].sum(axis=0)/nt
        v=raw*np.array([f,1-f])[:,None,None]
        return raw,np.concatenate([v,v.sum(axis=0,keepdims=True)]),unmatched
    def project(v,D,W,o1,o2):
        fixed=v@o1;free=v@o2.T;rf=v-fixed[...,None]*D[:,0];ru=v-free@D.T
        values=np.stack([fixed,free[...,0],free[...,1],abs(rf).sum(axis=-1)/2,abs(ru).sum(axis=-1)/2,
            np.sqrt(np.maximum(np.einsum('...i,ij,...j->...',rf,W,rf),0)),
            np.sqrt(np.maximum(np.einsum('...i,ij,...j->...',ru,W,ru),0))],axis=-1)
        return values,rf,ru
    # Only three predeclared event-weight reconstructions; no full new Fisher bootstrap.
    draws={}
    for role in ['cal','eval']:
        take=d['role']==role;groups=np.unique(d['group'][take]);rng=np.random.default_rng(p['bootstrap_seeds'][role]);matrix=np.zeros((500,len(groups)),int)
        for component in ['pi','k','charm']:
            ix=[i for i,g in enumerate(groups) if str(g).startswith(component+':')]
            if ix:matrix[:,ix]=rng.multinomial(len(ix),[1/len(ix)]*len(ix),size=500)
        draws[role]=[matrix[b,np.searchsorted(groups,d['group'][take])] for b in p['independent_QA_bootstrap_indices']]
        for j,b in enumerate(p['independent_QA_bootstrap_indices']):
            w=draws[role][j];low=d['low'][take]
            ess=[w[m].sum()**2/(w[m]**2).sum() for m in [np.ones(len(w),bool),low,~low]]
            check('ESS',ess,boot[role+'_ESS'][b])
    support=read(OUT/'support.csv');vector_rows=read(OUT/'vectors.csv');residual_rows=read(OUT/'residuals.csv')
    projection_rows=read(OUT/'projections.csv')
    for role in ['cal','eval']:
        h,_,layer=event_counts(role,'M_mu');take=d['role']==role;low=d['low'][take];groups=d['group'][take]
        for c,component in enumerate(['low','high']):
            for k in range(27):
                row=next(r for r in support if r['component']==component and int(r['stratum'])==k)
                count=int(h[c,k].sum());sources=len(np.unique(groups[(layer==k)&(low==(c==0))]))
                assert count==int(row[role+'_N']) and sources==int(row[role+'_sources'])
                assert int((boot[role+'_stratum_counts'][:,c,k]==0).sum())==int(row['bootstrap_'+role+'_zero_N'])
    for row in support:
        c=['low','high'].index(row['component']);k=int(row['stratum'])
        actual=((boot['cal_stratum_counts'][:,c,k]>0)&(boot['eval_stratum_counts'][:,c,k]>0)).sum()
        assert actual==int(row['bootstrap_shared_N'])
    for row,model in zip(summary['Fisher'],models):
        rep=row['representation'];finite=row['finite_MC'];key=f'{rep}_{"finite" if finite else "known"}'
        t,h,_=event_counts('cal',rep);r,_,_=event_counts('eval',rep);D,W,I,o1,o2,values=solve(t,h,finite)
        check('direction',D,model['D']);check('covariance_inverse',W,model['inverse_covariance']);check('Fisher',I,row['fisher']);check('operator',o2,model['free_operator'])
        check('sigma',values[:3],[row['sigma_f_fixed'],row['sigma_f_free'],row['sigma_alpha']]);check('sigma',row['sigma_f_fixed'],information(t.sum(axis=1),f,1000,finite))
        check('sigma',row['sigma_f_free'],row['Schur_sigma_f'])
        high=(d['role']=='cal')&(~d['low']);u=np.log(d['truth_E_GeV'][high]/400);bins=d[rep][high];step=p['derivative_difference_step']
        def tilt(alpha):
            w=np.exp(alpha*u);return np.bincount(bins,weights=w,minlength=17)/w.sum()
        check('derivative',(tilt(step)-tilt(-step))/(2*step),D[:,1]/(1-f))
        raw,v,unmatched=direct_vectors(t,r);result,rf,ru=project(v,D,W,o1,o2)
        for c,component in enumerate(COMPONENTS):
            for j,term in enumerate(TERMS):
                for k,field in enumerate(summary['projection_bootstrap_fields']):
                    saved=next(x for x in projection_rows if x['representation']==rep and x['finite_MC']==str(finite) and x['component']==component and x['term']==term and x['quantity']==field)
                    check('vectors',result[c,j,k],float(saved['central']))
        saved=[float(x['delta_probability']) for x in vector_rows if x['representation']==rep]
        check('vectors',raw.reshape(-1),saved)
        for mode,res in [('fixed',rf),('free',ru)]:
            saved=[float(x['delta_probability']) for x in residual_rows if x['representation']==rep and x['finite_MC']==str(finite) and x['mode']==mode]
            check('residuals',res.reshape(-1),saved)
        for j,b in enumerate(p['independent_QA_bootstrap_indices']):
            bt,bh,_=event_counts('cal',rep,draws['cal'][j]);br,_,_=event_counts('eval',rep,draws['eval'][j]);bD,bW,bI,bo1,bo2,bval=solve(bt,bh,finite)
            check('bootstrap_Fisher',bval,boot[key+'_Fisher'][b]);_,bv,unmatched=direct_vectors(bt,br)
            bp,_,_=project(bv,bD,bW,bo1,bo2);check('bootstrap_projection',bp,boot[key+'_projection'][b])
            np.testing.assert_allclose(unmatched,boot[rep+'_unmatched_mass'][b],atol=1e-12,rtol=0)
    invalid={key:int((~np.isfinite(boot[key])).sum()) for key in boot.files}
    save(OUT/'verification.json',dict(passed=True,method='independent event weights and explicit strata; reduced simplex covariance inverse',
        central_models=4,bootstrap_indices=p['independent_QA_bootstrap_indices'],bootstrap_models=12,
        max_absolute_differences=errors,invalid_entries=invalid,protected_counts=protected,binning_support_protection_pass=True))
    # Read the existing stage65 results; do not rerun train-source inference.
    previous=json.loads((prior/'summary.json').read_text());old_intervals=read(prior/'Fisher_intervals.csv');new_intervals=read(OUT/'Fisher_intervals.csv')
    comparison=[]
    for row in summary['Fisher']:
        old=next(x for x in previous['Fisher'] if x['point']=='eval' and x['representation']==row['representation'] and x['finite_MC']==row['finite_MC'])
        for field in ['sigma_f_fixed','sigma_f_free','sigma_alpha','parameter_correlation','sigma_f_cost_ratio']:
            base=dict(representation=row['representation'],finite_MC=row['finite_MC'],quantity=field,train_central=old[field],cal_central=row[field])
            for role,rows in [('train',old_intervals),('cal',new_intervals)]:
                interval=next(x for x in rows if x.get('point','eval')=='eval' and x['representation']==row['representation'] and x['finite_MC']==str(row['finite_MC']) and x['quantity']==field)
                base.update({role+'_'+k:interval[k] for k in ['low95','high95','valid_replicates','invalid_replicates']})
            comparison.append(base)
    table(OUT/'template_comparison.csv',comparison)
    new_proj=read(OUT/'projections.csv');old_proj=[x for x in read(prior/'projections.csv') if x['point']=='eval']
    comparison=[]
    for row in new_proj:
        old=next(x for x in old_proj if all(x[k]==row[k] for k in ['representation','finite_MC','component','term','quantity']))
        base={k:row[k] for k in ['representation','finite_MC','component','term','quantity']}
        for role,x in [('train',old),('cal',row)]:base.update({role+'_'+k:x[k] for k in ['central','low95','high95','valid_replicates','invalid_replicates']})
        comparison.append(base)
    table(OUT/'projection_comparison.csv',comparison)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,3.6))
    for rep,color in [('M_mu','tab:blue'),('S_scalar','tab:orange')]:
        new=next(r for r in summary['Fisher'] if r['representation']==rep and r['finite_MC'])
        old=next(r for r in previous['Fisher'] if r['point']=='eval' and r['representation']==rep and r['finite_MC'])
        for mode,style in [('fixed','o--'),('free','s-')]:axes[0].plot([0,1],[100*x['sigma_r_over_r_'+mode] for x in [old,new]],style,color=color,label=rep[0]+' '+mode)
        axes[1].plot([0,1],[x['parameter_correlation'] for x in [old,new]],'o-',color=color,label=rep[0])
        axes[2].plot([0,1],[x['sigma_f_cost_ratio'] for x in [old,new]],'o-',color=color)
    for ax in axes:ax.set_xticks([0,1],['train template','cal template']);ax.grid(alpha=.25)
    axes[0].set_ylabel(r'Local $\sigma_r/r$ [%]');axes[0].legend(fontsize=8);axes[1].set_ylabel(r'Correlation $(f,\alpha)$');axes[2].set_ylabel('Free / fixed uncertainty')
    fig.suptitle(r'Eval f fixed; selected N=1000; finite MC; local $\alpha=0$');fig.tight_layout();fig.savefig(OUT/'template_information.png',dpi=140);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(12,3.6))
    labels=[]
    for i,(rep,term) in enumerate([(r,t) for r in REPRESENTATIONS for t in ['mixture','conditional','total']]):
        labels.append(rep[0]+' '+term[:4])
        for role,dx,color in [('train',-.12,'tab:blue'),('cal',.12,'tab:orange')]:
            for ax,quantity,scale in [(axes[0],'free_delta_f',100),(axes[1],'free_delta_alpha',1),(axes[2],'free_weighted_norm',1)]:
                row=next(x for x in comparison if x['representation']==rep and x['finite_MC']=='True' and x['component']=='combined' and x['term']==term and x['quantity']==quantity)
                v,lo,hi=[float(row[role+'_'+k])*scale for k in ['central','low95','high95']]
                ax.vlines(i+dx,lo,hi,color=color);ax.plot(i+dx,v,'o',color=color,label=role if i==0 else None)
    for ax in axes:ax.set_xticks(range(6),labels,rotation=30);ax.axhline(0,color='gray',lw=.5);ax.grid(alpha=.25)
    axes[0].set_ylabel(r'Free $\delta f$ [percentage points]');axes[0].legend(fontsize=8);axes[1].set_ylabel(r'Free $\delta\alpha$');axes[2].set_ylabel('Free residual weighted norm')
    fig.suptitle('Eval response shift, separate-template source intervals (not a paired difference)');fig.tight_layout();fig.savefig(OUT/'template_projections.png',dpi=140);plt.close(fig)
    save(OUT/'report_resources.json',resources(start));print(json.dumps(errors,indent=2))


if __name__=='__main__':main()
