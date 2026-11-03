"""Fixed stage87 bounded and physical muon/transfer mixture candidates."""
import argparse
import json
import math
import time

import numpy as np
import torch
from scipy.optimize import minimize
from scipy.special import ndtr, logsumexp

from audited_features import configuration
from support_augmentation import arrays, save, table, begin, resources
from resplit_energy import OUT,CACHE,ART

M=.1056583755
LOG2PI=math.log(2*math.pi)


class Network(torch.nn.Module):
    def __init__(self,n,kind):
        super().__init__();self.kind=kind
        self.body=torch.nn.Sequential(torch.nn.Linear(n,64),torch.nn.SiLU(),torch.nn.Linear(64,64),torch.nn.SiLU())
        self.head=torch.nn.Linear(64,2 if kind=='bounded' else 15)
        torch.nn.init.zeros_(self.head.weight);torch.nn.init.zeros_(self.head.bias)
        if kind=='posterior':
            with torch.no_grad():
                self.head.bias[6:9]=torch.tensor([0.,-2.,1.])
                self.head.bias[9:12]=math.log((.5-.05)/(5-.5))
                self.head.bias[12:15]=math.log((1.-.05)/(5-1.))

    def forward(self,x):return self.head(self.body(x))


def parameters(v):
    q=v.reshape(-1,5,3)
    return torch.log_softmax(q[:,0],1),q[:,1],q[:,2],.05+4.95*torch.sigmoid(q[:,3]),.05+4.95*torch.sigmoid(q[:,4])


def nodes(n=32):
    x,w=np.polynomial.hermite.hermgauss(n)
    return x*math.sqrt(2),w/math.sqrt(math.pi)


def tensor_nodes(n=32,dtype=torch.float32):
    x,w=nodes(n);return torch.tensor(x,dtype=dtype),torch.tensor(np.log(w),dtype=dtype)


def normal_log(v,mu,sig):return -.5*((v-mu)/sig)**2-torch.log(sig)-.5*LOG2PI


def log_energy_density(v,logE,pz,b=0.,T=1.,quadrature=32):
    lp,mr,ms,sr,ss=parameters(v);mr=mr+b;sr=sr*T
    x,lw=tensor_nodes(quadrature,v.dtype)
    samples=ms[:,:,None]+ss[:,:,None]*x
    log_onef=torch.cat([torch.log(.9+.1*torch.sigmoid(-samples[:,:1])),math.log(.9)+torch.nn.functional.logsigmoid(-samples[:,1:])],1)
    mu=torch.exp(logE[:,None,None]+log_onef);delta=mu-M;ok=delta>0
    safe=torch.where(ok,delta,torch.ones_like(delta));r=torch.log(safe/pz[:,None,None])
    # Density in log(E/GeV): dr/dlogE = E*(1-f)/(E*(1-f)-m).
    density=normal_log(r,mr[:,:,None],sr[:,:,None])+logE[:,None,None]+log_onef-torch.log(safe)
    density=torch.where(ok,density,torch.full_like(density,-1e30))
    return torch.logsumexp(lp+torch.logsumexp(density+lw,2),1)


def joint_density(v,mu,f,pz,valid):
    lp,mr,ms,sr,ss=parameters(v)
    safe_mu=torch.where(valid,mu,torch.ones_like(mu));r=torch.log((safe_mu-M)/pz)
    aa=torch.tensor([0.,.1,.1],dtype=v.dtype)[None,:];width=torch.tensor([.1,.9,.9],dtype=v.dtype)[None,:]
    t=(f[:,None]-aa)/width;inside=(t>0)&(t<1)
    safe=torch.where(inside,t,torch.full_like(t,.5));s=torch.log(safe)-torch.log1p(-safe)
    logf=normal_log(s,ms,ss)-torch.log(width)-torch.log(safe)-torch.log1p(-safe)
    logf=torch.where(inside,logf,torch.full_like(logf,-1e30))
    boundary=valid&((f==0)|(f==.1))
    if boundary.any():
        lo=torch.maximum(f[:,None]-5e-7,aa);hi=torch.minimum(f[:,None]+5e-7,aa+width)
        low=(lo-aa)/width;high=(hi-aa)/width
        def cdf(t):
            inner=(t>0)&(t<1);ts=torch.where(inner,t,torch.full_like(t,.5))
            z=(torch.log(ts)-torch.log1p(-ts)-ms)/ss
            out=.5*(1+torch.erf(z/math.sqrt(2)))
            return torch.where(t<=0,torch.zeros_like(out),torch.where(t>=1,torch.ones_like(out),out))
        probability=torch.where(hi>lo,cdf(high)-cdf(low),torch.zeros_like(high))
        censored=torch.log(torch.clamp(probability,min=1e-30))
        logf=torch.where(boundary[:,None],censored,logf)
    terms=lp+normal_log(r[:,None],mr,sr)-torch.log(safe_mu[:,None]-M)+logf
    terms=torch.where(valid[:,None],terms,torch.zeros_like(terms))
    return torch.where(valid,torch.logsumexp(terms,1),torch.zeros_like(mu))


def preprocess(d,p):
    idx=[configuration()['features'].index(n) for n in p['features']];a=d['x'][:,idx].astype(float);tr=d['role']==1
    med=np.nanmedian(a[tr],axis=0);med=np.where(np.isfinite(med),med,0.)
    q=np.nanquantile(a[tr],[.25,.75],axis=0);scale=q[1]-q[0];scale=np.where(np.isfinite(scale)&(scale>0),scale,1.)
    missing=np.isnan(a);z=(np.where(missing,med,a)-med)/scale;clipped=(abs(z)>20)&~missing
    z=np.clip(z,-20,20)
    flags=np.column_stack([d[k] for k in ['wave_invalid','fit_failure','calo_invalid']])
    x=np.column_stack([z,missing,flags]).astype('float32');assert np.isfinite(x).all()
    return x,dict(median=med.tolist(),IQR=scale.tolist(),features=p['features'],normalized_cap=20,
                 clipping_counts_by_role={str(r):int(clipped[d['role']==r].sum()) for r in [0,1,2,3]},input_dimensions=x.shape[1])


def predict_network(model,x):
    with torch.no_grad():return np.concatenate([model(torch.tensor(x[j:j+2048])).numpy() for j in range(0,len(x),2048)])


def numpy_parameters(v,b=0.,T=1.):
    q=v.reshape(-1,5,3).astype(float);lp=q[:,0]-logsumexp(q[:,0],axis=1)[:,None]
    sig=lambda v:1/(1+np.exp(-np.clip(v,-700,700)))
    return lp,q[:,1]+b,q[:,2],(.05+4.95*sig(q[:,3]))*T,.05+4.95*sig(q[:,4])


def cdf(logE,pz,params,quadrature=32):
    lp,mr,ms,sr,ss=params;x,w=nodes(quadrature)
    samples=ms[:,:,None]+ss[:,:,None]*x
    low=.9+.1/(1+np.exp(np.clip(samples[:,:1],-700,700)))
    high=.9/(1+np.exp(np.clip(samples[:,1:],-700,700)))
    delta=np.exp(logE)[:,None,None]*np.concatenate([low,high],axis=1)-M
    r=np.log(np.maximum(delta,np.finfo(float).tiny)/pz[:,None,None])
    val=np.where(delta>0,ndtr((r-mr[:,:,None])/sr[:,:,None]),0.)
    return np.sum(np.exp(lp)*np.sum(val*w,axis=2),axis=1)


def prior_setup(d):
    edges=np.array([0,50,100,200,400,800,1600,3200,6400,np.inf]);tr=d['role']==1
    ids=np.searchsorted(edges,d['truth_E_GeV'],side='right')-1
    train=np.bincount(ids[tr],weights=d['weight'][tr],minlength=9)+.5;train/=train.sum()
    nominal=tr&d['nominal'];cnt=np.bincount(d['key_id'][nominal]);wn=1/cnt[d['key_id'][nominal]]
    target=np.bincount(ids[nominal],weights=wn,minlength=9)+.5;target/=target.sum()
    pressure=target.copy();pressure[:3]*=4;pressure/=pressure.sum()
    flat=train.copy();flat[1:8]=(1-flat[[0,8]].sum())/7
    ratios={k:np.clip(v/train,.1,10) for k,v in dict(nominal=target,flat=flat,pressure=pressure,training=train).items()}
    return edges,ratios,dict(edges_GeV=['inf' if np.isinf(x) else x for x in edges],training_mass=train.tolist(),nominal_mass=target.tolist(),
        pressure_mass=pressure.tolist(),flat_mass=flat.tolist(),ratios={k:v.tolist() for k,v in ratios.items()},nominal_training_N=int(nominal.sum()),
        assumption='invariant p(x|E) for prior shift, unverified; only sensitivity, no extra training')


def posterior_summary(v,pz,truth,edges,ratios,b=0.,T=1.,quadrature=32,median_only=False):
    output={};params=numpy_parameters(v,b,T)
    F=np.column_stack([np.zeros(len(v))]+[cdf(np.full(len(v),np.log(e)),pz,params,quadrature) for e in edges[1:-1]]+[np.ones(len(v))])
    mass=np.maximum(np.diff(F,axis=1),0);pit=cdf(np.log(truth),pz,params,quadrature)
    with torch.no_grad():
        density=log_energy_density(torch.tensor(v,dtype=torch.float64),torch.tensor(np.log(truth)),torch.tensor(pz),b,T,quadrature).numpy()
    for name,ratio in ratios.items():
        weighted=mass*ratio;norm=weighted.sum(1);prefix=np.column_stack([np.zeros(len(v)),np.cumsum(weighted,axis=1)])
        def target_cdf(z):
            raw=cdf(z,pz,params,quadrature);ix=np.searchsorted(edges,np.exp(z),side='right')-1;ix=np.clip(ix,0,8)
            return (prefix[np.arange(len(v)),ix]+ratio[ix]*(raw-F[np.arange(len(v)),ix]))/norm
        quantiles=[('median',.5)] if median_only else [('q05',.05),('q16',.16),('median',.5),('q84',.84),('q95',.95)]
        for label,q in quantiles:
            lo=np.full(len(v),np.log(M)+1e-12);hi=np.log(pz)+40
            for _ in range(40):
                mid=(lo+hi)/2;above=target_cdf(mid)>=q;hi=np.where(above,mid,hi);lo=np.where(above,lo,mid)
            output[name+'_'+label]=(lo+hi)/2
        ix=np.clip(np.searchsorted(edges,truth,side='right')-1,0,8)
        output[name+'_pit']=(prefix[np.arange(len(v)),ix]+ratio[ix]*(pit-F[np.arange(len(v)),ix]))/norm
        output[name+'_ESS_fraction']=norm**2/(mass*(ratio**2)).sum(1)
        output[name+'_logscore']=density+np.log(ratio[ix])-np.log(norm)
    return output


def mathematical_qa():
    torch.set_num_threads(1);torch.manual_seed(2026110387)
    model=Network(85,'posterior');x=torch.zeros((12,85));v=model(x)
    pz=torch.linspace(55,1000,12);f=torch.tensor([.02,.05,.09,.12,.3,.6,.8,.95,.1,0.,.04,.5]);mu=pz*1.02
    enu=mu/(1-f);valid=torch.ones(12,dtype=torch.bool)
    loss=-joint_density(v,mu,f,pz,valid).mean()-.25*log_energy_density(v,torch.log(enu),pz).mean()
    loss.backward();assert torch.isfinite(loss) and all(torch.isfinite(p.grad).all() for p in model.parameters())
    vv=v.detach().numpy();pp=pz.numpy().astype(float);params=numpy_parameters(vv)
    probs=cdf(np.log(enu.numpy()),pp,params)
    assert ((probs>=0)&(probs<=1)).all()
    np.testing.assert_allclose(cdf(np.log(pp)+40,pp,params),1,atol=1e-12)
    np.testing.assert_allclose(cdf(np.full(12,np.log(M)),pp,params),0,atol=1e-12)
    torchval=log_energy_density(v.detach(),torch.log(enu),pz).numpy()
    # Independent finite difference of analytic CDF checks the energy Jacobian.
    z=np.log(enu.numpy().astype(float));eps=1e-4
    numeric=(cdf(z+eps,pp,params)-cdf(z-eps,pp,params))/(2*eps)
    err=float(np.max(abs(np.exp(torchval)-numeric)));assert err<2e-4,err
    return dict(passed=True,synthetic_analytic_cases=12,censored_boundaries_included=True,finite_forward_backward=True,
                optimizer_steps=0,max_CDF_density_absolute_difference=err)


def qa():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());d=arrays(CACHE/'input.npz')
    positions=np.concatenate([np.flatnonzero(d['role']==r)[:13] for r in [1,2,3]])
    assert len(positions)==39; positions=np.r_[positions,np.flatnonzero(d['role']==0)[:1]]
    assert len(positions)==40
    from latent_transfer_diagnostics import check_x
    check_x(d['x'][positions]);q=mathematical_qa()
    assert p['limits']['formal_energy_models']==5
    save(OUT/'fit_input_QA.json',dict(cache_identities=40,identity_positions=positions.tolist(),
         torch_version=torch.__version__,**q,**resources(start)))
    print('40 actual input identities and12 analytic density/boundary cases passed; zero optimizer steps',flush=True)


def train_network(kind,x,d,p):
    start=begin();torch.manual_seed(p['shared_capacity']['seed']);model=Network(x.shape[1],kind)
    optimizer=torch.optim.Adam(model.parameters(),lr=.001)
    tr=np.flatnonzero(d['role']==1);xx=torch.tensor(x[tr]);pz=torch.tensor(d['pz'][tr],dtype=torch.float32)
    y=torch.tensor(np.log(d['truth_E_GeV'][tr]),dtype=torch.float32)
    valid=torch.tensor(d['label_physical'][tr]);mu=torch.tensor(np.where(d['label_physical'][tr],d['mu_truth_GeV'][tr],1.),dtype=torch.float32)
    f=torch.tensor(np.where(d['label_physical'][tr],d['y_lepton'][tr],0.),dtype=torch.float32)
    w=torch.tensor(d['weight'][tr]/d['weight'][tr].mean(),dtype=torch.float32)
    rng=np.random.default_rng(p['shared_capacity']['seed']);records=[]
    for epoch in range(150):
        perm=rng.permutation(len(tr));total=0.
        for j in range(0,len(tr),1024):
            ix=perm[j:j+1024];v=model(xx[ix]);optimizer.zero_grad()
            if kind=='bounded':
                correction=torch.sigmoid(v[:,0])*math.log(64)*torch.tanh(v[:,1]);pred=torch.log(pz[ix]/.8)+correction
                gate=torch.nn.functional.binary_cross_entropy_with_logits(v[:,0],(f[ix]>=.2).float(),reduction='none')
                loss=(w[ix]*((pred-y[ix])**2+.1*gate*valid[ix])).mean()
            else:
                joint=joint_density(v,mu[ix],f[ix],pz[ix],valid[ix])
                marginal=log_energy_density(v,y[ix],pz[ix])
                loss=(w[ix]*(-joint-.25*marginal)).mean()
            assert torch.isfinite(loss),(kind,epoch,j,float(loss))
            loss.backward();norm=torch.nn.utils.clip_grad_norm_(model.parameters(),10.,error_if_nonfinite=True);optimizer.step()
            total+=float(loss.detach())*len(ix)
        if (epoch+1)%25==0:
            rec=dict(model=kind,epoch=epoch+1,train_loss=total/len(tr),wall_s=time.perf_counter()-start[0]);records.append(rec);print(json.dumps(rec),flush=True)
        assert time.process_time()-start[1]<2800,'fixed fit CPU budget exceeded; do not select a shortened fit'
    path=ART/f'{kind}.pt';torch.save(dict(state_dict=model.state_dict(),kind=kind,input_dimensions=x.shape[1]),path)
    back=Network(x.shape[1],kind);back.load_state_dict(torch.load(path,weights_only=True)['state_dict'])
    with torch.no_grad():np.testing.assert_array_equal(model(torch.tensor(x[:40])).numpy(),back(torch.tensor(x[:40])).numpy())
    table(OUT/f'training_{kind}.tsv',records)
    return model,dict(model=kind,epochs=150,model_reload_exact=True,**resources(start))


def calibrate_posterior(v,d,ix):
    vv=torch.tensor(v,dtype=torch.float64);y=torch.tensor(np.log(d['truth_E_GeV'][ix]),dtype=torch.float64)
    pz=torch.tensor(d['pz'][ix],dtype=torch.float64);ww=torch.tensor(d['weight'][ix]/d['weight'][ix].sum(),dtype=torch.float64)
    def objective(values):
        b=torch.tensor(values[0],dtype=torch.float64,requires_grad=True);T=torch.tensor(values[1],dtype=torch.float64,requires_grad=True)
        total=0.;gb=0.;gt=0.
        for j in range(0,len(ix),1024):
            loss=-(ww[j:j+1024]*log_energy_density(vv[j:j+1024],y[j:j+1024],pz[j:j+1024],b,T)).sum()
            loss.backward();total+=float(loss.detach())
        return total,np.array([float(b.grad),float(T.grad)])
    result=minimize(objective,[0.,1.],jac=True,bounds=[(-.2,.2),(.5,2)],method='L-BFGS-B',options=dict(maxiter=100))
    assert np.isfinite(result.fun) and np.isfinite(result.x).all()
    return result.x,dict(b=float(result.x[0]),T=float(result.x[1]),success=bool(result.success),message=str(result.message),iterations=int(result.nit),cal_logE_NLL=float(result.fun))


def fit():
    import xgboost as xgb
    start=begin();torch.set_num_threads(1);p=json.loads((OUT/'protocol.json').read_text());d=arrays(CACHE/'input.npz')
    assert not ART.exists(),'formal models already started; do not rerun'
    ART.mkdir(parents=True);(ART/'started.txt').write_text('fixed three direct seeds plus two neural candidates\n')
    qa();tr=d['role']==1;cal=d['role']==2;active=d['role']>0;ix=np.flatnonzero(active);ci=np.flatnonzero(cal)
    y=np.log(d['truth_E_GeV']);names=configuration()['features'];w=d['weight'];records=[]
    train=xgb.DMatrix(d['x'][tr],label=y[tr],weight=w[tr],feature_names=names,nthread=1)
    target=xgb.DMatrix(d['x'][active],feature_names=names,nthread=1);direct=[]
    init=float(np.average(y[tr],weights=w[tr]))
    for seed in p['baseline']['seeds']:
        tick=begin();params=dict(p['baseline']['xgboost'],seed=seed,base_score=init,boost_from_average=0)
        model=xgb.train(params,train,num_boost_round=400);path=ART/f'direct_{seed}.ubj';model.save_model(path)
        back=xgb.Booster(params={'nthread':1});back.load_model(path)
        val=model.predict(target).astype(float);np.testing.assert_array_equal(val,back.predict(target));direct.append(val)
        records.append(dict(model='direct',seed=seed,rounds=400,model_reload_exact=True,params=params,**resources(tick)))
    pred={k:d[k] for k in d if k!='x'};offsets={}
    raw=np.full(len(y),np.nan);raw[active]=np.mean(direct,axis=0);off=float(np.average(y[cal]-raw[cal],weights=w[cal]))
    pred.update(direct_raw=raw,direct_cal=raw+off);offsets['direct']=off
    x,normalization=preprocess(d,p);save(OUT/'normalization.json',normalization)
    for kind in ['bounded','posterior']:
        model,rec=train_network(kind,x,d,p);records.append(rec);v=predict_network(model,x[active])
        if kind=='bounded':
            corr=(1/(1+np.exp(-v[:,0])))*math.log(64)*np.tanh(v[:,1]);raw=np.full(len(y),np.nan);raw[active]=np.log(d['pz'][active]/.8)+corr
            off=float(np.average(y[cal]-raw[cal],weights=w[cal]));pred.update(bounded_raw=raw,bounded_cal=raw+off);offsets['bounded']=off
        else:
            vc=v[d['role'][active]==2];(b,T),calibration=calibrate_posterior(vc,d,ci);save(OUT/'posterior_calibration.json',calibration)
            edges,ratios,prior=prior_setup(d);save(OUT/'prior.json',prior)
            result={}
            for j in range(0,len(ix),1024):
                ids=ix[j:j+1024];vv=v[j:j+1024]
                ss=posterior_summary(vv,d['pz'][ids],d['truth_E_GeV'][ids],edges,ratios,b,T)
                for key,value in ss.items():result.setdefault(key,np.full(len(y),np.nan))[ids]=value
            pred.update({'posterior_'+k:vv for k,vv in result.items()})
            # Raw training-prior median, fixed diagnostic, not a chosen replacement.
            for j in range(0,len(ix),1024):
                ids=ix[j:j+1024];ss=posterior_summary(v[j:j+1024],d['pz'][ids],d['truth_E_GeV'][ids],edges,{'training':np.ones(9)},median_only=True)
                pred.setdefault('posterior_raw',np.full(len(y),np.nan))[ids]=ss['training_median']
            np.savez_compressed(ART/'posterior_parameters.npz',row=ix,head=v,b=np.array(b),T=np.array(T))
            # Fixed32 is main; sensitivity to64/128 is reported without selecting a winner.
            qi=ci[:40];local=np.searchsorted(ix,qi);vals=[]
            for nq in [32,64,128]:
                zz=cdf(np.log(d['truth_E_GeV'][qi]),d['pz'][qi],numpy_parameters(v[local],b,T),nq);vals.append(zz)
            save(OUT/'quadrature_QA.json',dict(identities=qi.tolist(),sample='first40 cal; fixed without loss selection',main_nodes=32,
                 max_abs_PIT_32_64=float(np.max(abs(vals[0]-vals[1]))),max_abs_PIT_64_128=float(np.max(abs(vals[1]-vals[2]))),
                 meaning='numerical sensitivity, not physics/MC uncertainty; main never replaced using test'))
        print(json.dumps(rec),flush=True)
    save(OUT/'fit.json',dict(status='completed',formal_energy_models=5,pilot_optimizer_steps=0,records=records,offsets=offsets,
         train_weighted_mean_logE=init,**resources(start)))
    np.savez_compressed(ART/'predictions.npz',**pred)
    from report_resplit_energy import report
    report()
    from validate_resplit_energy import validate
    validate()
    # Keep only compact, reviewable prediction rows; rich temporary arrays and
    # bootstrap multiplicities can be reconstructed from the frozen code/seed.
    keep=['direct_raw','direct_cal','bounded_raw','bounded_cal','posterior_raw']
    keep += ['posterior_'+s for s in ['training_median','nominal_median','flat_median','pressure_median',
             'nominal_q05','nominal_q16','nominal_q84','nominal_q95','nominal_pit','nominal_ESS_fraction','nominal_logscore']]
    compact={k:pred[k][active] for k in keep+['truth_E_GeV','y_lepton','confirmed','pz','input_missing']}
    compact['row']=ix;compact['role']=d['role'][active];compact['weight']=d['weight'][active]
    np.savez_compressed(ART/'predictions.npz',**compact)
    (ART/'bootstrap.npz').unlink()
    save(OUT/'retention.json',dict(compact_predictions=True,active_rows=len(ix),
         rich_prediction_table_validated_before_compaction=True,all500_draw_arrays_validated_then_removed=True,
         reconstruction='original immutable caches + split.npz + saved parameters/calibration/normalization + protocol seed reproduce rich metrics without retraining'))
    (ART/'started.txt').unlink()
    save(OUT/'total_fit_job_resources.json',resources(start))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','fit']);globals()[p.parse_args().action]()
