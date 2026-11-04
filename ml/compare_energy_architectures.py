"""Stage94 frozen five-cell study on audited stage87 data, GPU fitting only."""
import argparse
import copy
import json
import math
import resource
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from audited_features import REPO, configuration
from retrain_accurate_posterior import reconstruct, qa_rows, original_protocol
from support_augmentation import arrays, save, table, begin, resources

OUT=REPO/'workbook/stage94_energy_ml'
CACHE=REPO/'ntuples/energy_ml_stage94'
ART=REPO/'ml/artifacts/stage94'
SEED=2026110494
CELLS=list('ABCDE')


def cal_partition():
    d=arrays(REPO/'ntuples/energy_ml_stage92/input_cal.npz')
    rng=np.random.default_rng(SEED);assignment={}
    for component in ['pi','k','charm']:
        gg=rng.permutation(np.unique(d['group'][d['component']==component]))
        for j,g in enumerate(gg):assignment[str(g)]=1 if j<len(gg)//2 else 2
    initial=np.array([assignment[str(g)] for g in d['group']],np.int8)
    priority=np.zeros(d['key_id'].max()+1,np.int8);np.maximum.at(priority,d['key_id'],initial)
    role=np.where(initial==priority[d['key_id']],initial,0).astype(np.int8)
    weight=np.zeros(len(role))
    stats=[]
    for code,name in [(0,'purged_select'),(1,'cal_select'),(2,'cal_post')]:
        m=role==code;_,inv,count=np.unique(d['key_id'][m],return_inverse=True,return_counts=True)
        if code:weight[m]=1/count[inv]
        e=d['truth_E_GeV'][m]
        stats.append(dict(role=name,N=int(m.sum()),incoming=int(len(count)),groups=int(len(np.unique(d['group'][m]))),
             E50_100=int(((e>=50)&(e<100)).sum()),E100_200=int(((e>=100)&(e<200)).sum()),
             lowpz_trueE200=int(((d['pz'][m]<100)&(e>=200)).sum()),missing=int(d['input_missing'][m].sum())))
    valid=all(s['incoming']>=2000 and s['E50_100']>=50 and s['E100_200']>=150 and s['lowpz_trueE200']>=50 for s in stats[1:])
    assert not set(d['key_id'][role==1])&set(d['key_id'][role==2])
    assert not set(d['group'][role==1])&set(d['group'][role==2])
    if not valid:role[:]=2;weight=d['weight'].copy()
    return dict(valid=valid,assignment=assignment,counts=stats,eligibility='each>=2000incoming/50E50_100/150E100_200/50lowpztruehighE; fixed support thresholds, no risk selection',row=d['row'],role=role,weight=weight)


def representation(d,cell,state=None):
    cfg=configuration();names=original_protocol()['features'] if cell=='A' else cfg['features']
    ix=[cfg['features'].index(n) for n in names];v=d['x'][:,ix].astype(float);missing=np.isnan(v)
    typed=cell in 'CDE';tr=d['role']==1
    if state is None:
        scales=np.nanmedian(abs(v[tr]),axis=0);scales=np.where(np.isfinite(scales)&(scales>1e-8),scales,1.)
        kinds=[]
        for n in names:
            domain=cfg['rules'][n]['domain']
            kinds.append('log' if domain=='positive' else 'log1p' if domain in ['count','nonnegative'] else 'identity' if domain in ['boolean','charge_sign'] or 'allowed_values' in cfg['rules'][n] else 'asinh')
        state=dict(features=names,typed=typed,scale=scales.tolist(),transform=kinds,cap=None if typed else 20)
    a=v.copy()
    if typed:
        for j,(kind,scale) in enumerate(zip(state['transform'],state['scale'])):
            if kind=='log':a[:,j]=np.log(a[:,j]/scale)
            elif kind=='log1p':a[:,j]=np.log1p(a[:,j]/scale)
            elif kind=='asinh':a[:,j]=np.arcsinh(a[:,j]/scale)
    if 'median' not in state:
        med=np.nanmedian(a[tr],axis=0);med=np.where(np.isfinite(med),med,0.)
        q=np.nanquantile(a[tr],[.25,.75],axis=0);scale=q[1]-q[0];scale=np.where(np.isfinite(scale)&(scale>0),scale,1.)
        state.update(median=med.tolist(),IQR=scale.tolist())
    z=(np.where(missing,state['median'],a)-state['median'])/state['IQR'];sat=(abs(z)>20)&~missing
    if not typed:z=np.clip(z,-20,20)
    flags=np.column_stack([d[k] for k in ['wave_invalid','fit_failure','calo_invalid']])
    x=np.column_stack([z,missing,flags]).astype('float32');assert np.isfinite(x).all()
    stats=[dict(cell=cell,feature=n,transform=state['transform'][j] if typed else 'raw',scale=state['scale'][j] if typed else 1.,
        median=state['median'][j],IQR=state['IQR'][j],**{f'role{r}_missing':int(missing[d['role']==r,j].sum()) for r in [1,2,3]},
        **{f'role{r}_abs_standardized_gt20':int(sat[d['role']==r,j].sum()) for r in [1,2,3]}) for j,n in enumerate(names)]
    return x,state,stats


class MLP(nn.Module):
    def __init__(self,dim,kind,center):
        super().__init__();self.body=nn.Sequential(nn.Linear(dim,64),nn.SiLU(),nn.Linear(64,64),nn.SiLU())
        self.head=nn.Linear(64,9 if kind=='E' else 1);nn.init.zeros_(self.head.weight);nn.init.zeros_(self.head.bias)
        with torch.no_grad():
            if kind=='E':
                self.head.bias[3:6]=torch.tensor([-.4,0.,.4]);self.head.bias[6:9]=math.log(math.expm1(.45))
            else:self.head.bias.fill_(center)
    def forward(self,x):return self.head(self.body(x))


def make(cell,dim,center):
    if cell!='D':return MLP(dim,cell,center)
    from tabm import TabM
    return TabM.make(n_num_features=dim,cat_cardinalities=None,d_out=1,n_blocks=2,d_block=64,dropout=0.,k=32,num_embeddings=None)


def decode(v):
    return torch.log_softmax(v[:,:3],1),v[:,3:6],.05+torch.nn.functional.softplus(v[:,6:9])


def output(model,x,cell,anchor):
    v=model(x)
    if cell=='E':
        lp,mu,sig=decode(v);return anchor+(lp.exp()*mu).sum(1),v
    return v.reshape(len(x),-1).mean(1),v


def objective(model,x,y,w,anchor,cell):
    point,v=output(model,x,cell,anchor)
    if cell=='E':
        lp,mu,sig=decode(v);r=y-anchor
        loss=-torch.logsumexp(lp-.5*((r[:,None]-mu)/sig)**2-torch.log(sig)-.5*math.log(2*math.pi),1)
    else:loss=(v.reshape(len(x),-1)-y[:,None]).square().mean(1)
    return (w*loss).sum()/w.sum(),point


def qa():
    start=begin();OUT.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
    d=reconstruct(qa_rows());assert len(d['row'])==40;torch.set_num_threads(1);checks=[]
    for cell in CELLS:
        x,state,_=representation(d,cell);torch.manual_seed(SEED)
        model=make(cell,x.shape[1],6.).cuda();xx=torch.tensor(x,device='cuda');y=torch.tensor(np.log(d['truth_E_GeV']),dtype=torch.float32,device='cuda');w=torch.tensor(d['weight'],dtype=torch.float32,device='cuda');anchor=torch.tensor(np.log(d['pz']/.8),dtype=torch.float32,device='cuda')
        torch.cuda.synchronize();tick=time.perf_counter();loss,p=objective(model,xx,y,w,anchor,cell);loss.backward();torch.cuda.synchronize()
        assert torch.isfinite(loss) and all(torch.isfinite(v.grad).all() for v in model.parameters() if v.grad is not None)
        # Batch throughput QA repeats the same40 identities, zero optimizer steps.
        costs=[]
        repeat=torch.arange(1024,device='cuda')%40
        for _ in range(4):
            model.zero_grad();torch.cuda.synchronize();tick=time.perf_counter()
            batchloss,_=objective(model,xx[repeat],y[repeat],w[repeat],anchor[repeat],cell);batchloss.backward();torch.cuda.synchronize();costs.append(time.perf_counter()-tick)
        checks.append(dict(batch1024_forward_backward_wall_s=float(np.median(costs[1:])),cell=cell,N=40,input_dimensions=x.shape[1],parameters=sum(p.numel() for p in model.parameters()),loss=float(loss.detach()),forward_backward_wall_s=time.perf_counter()-tick,optimizer_steps=0))
    # Independent mixture values/CDF gradients on the fixed QA heads, not a network fit.
    from scipy.special import logsumexp,ndtr
    from scipy.stats import norm
    with torch.no_grad():v=model(xx);lp,mu,sig=decode(v)
    lp,mu,sig=[a.cpu().numpy().astype(float) for a in [lp,mu,sig]];yy=(y-anchor).cpu().numpy().astype(float)
    manual=logsumexp(lp+norm.logpdf(yy[:,None],mu,sig),axis=1)
    logden=np.log(np.sum(np.exp(lp)*np.exp(-.5*((yy[:,None]-mu)/sig)**2)/(sig*np.sqrt(2*np.pi)),axis=1))
    assert np.max(abs(manual-logden))<1e-12
    # Independent double precision finite differences for all nine MDN head coordinates.
    h=model(xx).detach().cpu().double().requires_grad_();target=(y-anchor).detach().cpu().double()
    ll,mm,ss=decode(h);values=torch.logsumexp(ll-.5*((target[:,None]-mm)/ss)**2-torch.log(ss)-.5*math.log(2*math.pi),1)
    gradient=torch.autograd.grad(values.sum(),h)[0].numpy();head=h.detach().numpy();finite=np.empty_like(head)
    def scalar_density(a):
        from scipy.special import logsumexp
        ll=a[:,:3]-logsumexp(a[:,:3],axis=1)[:,None];mu=a[:,3:6];sig=.05+np.logaddexp(0.,a[:,6:9])
        return logsumexp(ll-.5*((target.numpy()[:,None]-mu)/sig)**2-np.log(sig)-.5*math.log(2*math.pi),axis=1)
    for j in range(9):
        plus=head.copy();minus=head.copy();plus[:,j]+=1e-5;minus[:,j]-=1e-5;finite[:,j]=(scalar_density(plus)-scalar_density(minus))/2e-5
    gradient_difference=float(abs(finite-gradient).max());assert gradient_difference<1e-7
    saved=dict(MDN_head_gradient_finite_difference_max=gradient_difference,passed=True,identities=40,missing_train=21,missing_cal=6,new_optimizer_steps=0,checks=checks,MDN_density_independent_max_difference=float(abs(manual-logden).max()),**resources(start))
    save(OUT/'startup_QA.json',saved);print(json.dumps(saved),flush=True)


def prepare_protocol():
    OUT.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
    part=cal_partition();np.savez_compressed(CACHE/'cal_partition.npz',row=part.pop('row'),subrole=part.pop('role'),weight=part.pop('weight'))
    save(OUT/'cal_partition.json',part)
    names=configuration()['features'];old=original_protocol()['features'];save(OUT/'feature_difference.json',dict(A41=old,B62=names,added21=[n for n in names if n not in old]))
    save(OUT/'protocol.json',dict(stage=94,seed=SEED,extra_seeds=[SEED+1,SEED+2],cells=CELLS,cal_partition_valid=part['valid'],
       max_epochs=300,validation_every=5,patience_epochs=30,fixed_epochs_without_select=300,
       optimizer='Adam lr.001 default/no decay/clip10 all cells; TabM k32 2x64 ReLU no embedding/dropout0; others2x64SiLU; batch1024 numpy seeded permutation',
       losses='A-D incomingweighted per-member logMSE; E threeNormal residual MDN marginal NLL sigma=.05+softplus, point=meanlogE',
       representations='A41/B62 raw trainmedianIQR clip20; C/D/E62 typed positive log,nonnegative/count log1p,signed asinh except discrete identity; trainmedianabs scales,medianIQR no cap; same masks/status',
       checkpoint='weighted cal_select point logMSE minimum every5, improve strictly, patience30; E selection by same point risk, NLL also logged',
       extra_selection='before any newtest forward/risk; primary cal_select raw points: lexicographic worst RMSE ratio normalized by original gate limits, then mean of normalized ratios, then allMSE; max2cells each2seeds; no valid select => zeroextras',
       offsets='one cal_post weighted mean logtruth-point residual each raw model/ensemble; MDN all mixturemeans translated by sameoffset. Original baseline raw and oldcal and samepostoffset variants separate',
       input='same46575/11612/13189 and17657 quarantine; incomingweights,all1016K,missing21/6/5 retained',
       reliability='incoming targetempirical weights; E models trained same weights, no nominalprior reinterpretation. Overall and Xgroups fixed from cal inputs/status only; truthstrata diagnostic, no truthPIT uniformity gate',
       limits=dict(GPU_concurrency=1,GPU_task_wall_s=7200,cumulative_CPU_s=21600,retained_bytes=20000000),
       CPU_parallelism='user authorizes more CPU cores; reporting processes4, BLASthreads1, roles/layers partitioned; preserve exact draws. GPU worker CPUthreads1 avoids oversubscription',
       newfit_count_max=9,test_scope='developed pool heldout from newfits; no newblind/source95/promotion',posterior_moment='optional not required; not executed by main five-cell worker'))
    print(json.dumps(part),flush=True)


def fit_one(d,x,cell,seed,part):
    protocol=json.loads((OUT/'protocol.json').read_text());start=begin();tr=np.flatnonzero(d['role']==1);cal=np.flatnonzero(d['role']==2)
    lookup=np.searchsorted(part['row'],d['row'][cal]);np.testing.assert_array_equal(part['row'][lookup],d['row'][cal])
    val=cal[part['subrole'][lookup]==1];vw=part['weight'][lookup][part['subrole'][lookup]==1]
    y=np.log(d['truth_E_GeV']);anchor=np.log(d['pz']/.8);center=float(np.average(y[tr],weights=d['weight'][tr]))
    torch.manual_seed(seed);torch.cuda.manual_seed_all(seed);model=make(cell,x.shape[1],center).cuda();opt=torch.optim.Adam(model.parameters(),lr=.001)
    xt=torch.tensor(x[tr],device='cuda');yt=torch.tensor(y[tr],dtype=torch.float32,device='cuda');wt=torch.tensor(d['weight'][tr]/d['weight'][tr].mean(),dtype=torch.float32,device='cuda');at=torch.tensor(anchor[tr],dtype=torch.float32,device='cuda')
    xv=torch.tensor(x[val],device='cuda');yv=torch.tensor(y[val],dtype=torch.float32,device='cuda');wv=torch.tensor(vw,dtype=torch.float32,device='cuda');av=torch.tensor(anchor[val],dtype=torch.float32,device='cuda')
    best=float('inf');best_epoch=0;best_state=None;history=[];rng=np.random.default_rng(seed);steps=0
    torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize()
    for epoch in range(1,301):
        model.train();total=0.;den=0.
        order=rng.permutation(len(tr))
        for j in range(0,len(tr),1024):
            idx=order[j:j+1024]
            opt.zero_grad(set_to_none=True);loss,_=objective(model,xt[idx],yt[idx],wt[idx],at[idx],cell)
            assert torch.isfinite(loss);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),10,error_if_nonfinite=True);opt.step();steps+=1;total+=float(loss.detach())*float(wt[idx].sum());den+=float(wt[idx].sum())
        if epoch%5==0:
            model.eval()
            with torch.no_grad():
                val_loss,p=objective(model,xv,yv,wv,av,cell) if len(val) else (torch.tensor(float('nan')),torch.empty(0,device='cuda'))
                score=float(((p-yv)**2*wv).sum()/wv.sum()) if len(val) else 0.
            record=dict(epoch=epoch,train_objective=total/den,cal_select_point_MSE=score if len(val) else '未测量',cal_select_objective=float(val_loss) if len(val) else '未测量',**resources(start));history.append(record)
            if len(val) and score<best:best=score;best_epoch=epoch;best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
            table(OUT/f'learning_{cell}_{seed}.tsv',history)
            if len(val) and epoch-best_epoch>=30:break
    if best_state is not None:model.load_state_dict(best_state)
    model.eval();torch.cuda.synchronize();cost=dict(cell=cell,seed=seed,epochs=epoch,best_epoch=best_epoch if len(val) else epoch,optimizer_steps=steps,
       parameters=sum(p.numel() for p in model.parameters()),GPU_peak_allocated_MiB=torch.cuda.max_memory_allocated()/1024**2,**resources(start))
    torch.save(dict(cell=cell,seed=seed,state_dict=model.cpu().state_dict(),input_dimensions=x.shape[1],center=center),ART/f'{cell}_{seed}.pt');model.cuda()
    table(OUT/f'learning_{cell}_{seed}.tsv',history);save(OUT/f'fit_{cell}_{seed}.json',cost)
    print('fit',json.dumps(cost),flush=True)
    # Only selection predictions are materialized before all model/seed selection is fixed.
    with torch.no_grad():p=output(model,xv,cell,av)[0].cpu().numpy()
    return model,p,val


def ranking(d,pred,ids,w):
    e=d['truth_E_GeV'][ids];pz=d['pz'][ids];f=d['y_lepton'][ids];y=np.log(e)
    base=arrays(REPO/'ml/artifacts/stage87/predictions.npz');ii=np.searchsorted(base['row'],d['row'][ids]);np.testing.assert_array_equal(base['row'][ii],d['row'][ids])
    direct=base['direct_cal'][ii];traditional=np.log(pz/.8)
    masks=[(e>=50)&(e<100),(e>=100)&(e<200),np.ones(len(e),bool),e>=200,pz<100,(pz<100)&(e>=200),f>=.8,~d['confirmed'][ids]]
    vals=[]
    for j,m in enumerate(masks):
        ref=traditional if j<2 else direct;lim=1.05 if j<2 else 1.01 if j==2 else 1.03
        vals.append(float(np.sqrt(np.average((pred[m]-y[m])**2,weights=w[m])/np.average((ref[m]-y[m])**2,weights=w[m]))/lim))
    return dict(worst_normalized_ratio=max(vals),mean_normalized_ratio=float(np.mean(vals)),all_MSE=float(np.average((pred-y)**2,weights=w)),ratios=vals)


def worker():
    start=begin();torch.set_num_threads(1);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    ART.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    assert not (ART/'started.txt').exists();d=reconstruct(np.arange(89033));part=arrays(CACHE/'cal_partition.npz')
    np.testing.assert_array_equal(np.bincount(d['role']),[17657,46575,11612,13189]);(ART/'started.txt').write_text('one preregistered bounded architecture study\n')
    representations={};states={};allstats=[]
    for cell in CELLS:
        representations[cell],states[cell],ss=representation(d,cell);allstats+=ss
    save(OUT/'preprocessing.json',states);table(OUT/'feature_transforms.tsv',allstats)
    original=json.loads((REPO/'workbook/stage87_energy_ml/normalization.json').read_text());assert states['A']['median']==original['median'] and states['A']['IQR']==original['IQR']
    models={};ranks=[]
    for cell in CELLS:
        model,p,ids=fit_one(d,representations[cell],cell,SEED,part);models[f'{cell}_{SEED}']=model
        if len(ids):
            i=np.searchsorted(part['row'],d['row'][ids]);r=ranking(d,p,ids,part['weight'][i]);ranks.append(dict(cell=cell,**r))
    selected=[r['cell'] for r in sorted(ranks,key=lambda r:(r['worst_normalized_ratio'],r['mean_normalized_ratio'],r['all_MSE'],r['cell']))[:2]] if json.loads((OUT/'protocol.json').read_text())['cal_partition_valid'] else []
    save(OUT/'selection.json',dict(selected_for_two_extra_seeds=selected,ranking=ranks,new_test_forward_before_selection=0,rule='frozen protocol lexicographic risk',source95=False))
    for cell in selected:
        for seed in [SEED+1,SEED+2]:models[f'{cell}_{seed}']=fit_one(d,representations[cell],cell,seed,part)[0]
    active=np.flatnonzero(d['role']>0);pred={};heads={};anchor=np.log(d['pz']/.8)
    for name,model in models.items():
        cell=name[0];values=[];vv=[]
        with torch.no_grad():
            for ii in np.array_split(active,math.ceil(len(active)/2048)):
                p,v=output(model,torch.tensor(representations[cell][ii],device='cuda'),cell,torch.tensor(anchor[ii],dtype=torch.float32,device='cuda'));values.append(p.cpu().numpy())
                if cell=='E':vv.append(v.cpu().numpy())
        pred[name]=np.concatenate(values)
        if vv:heads[name]=np.concatenate(vv)
    for cell in selected:pred[cell+'_ensemble']=np.mean([pred[f'{cell}_{seed}'] for seed in [SEED,SEED+1,SEED+2]],axis=0)
    np.savez_compressed(ART/'point_predictions.npz',row=active,**pred)
    np.savez_compressed(ART/'MDN_heads.npz',row=active,**heads)
    keep=['row','role','weight','key_id','group','block','component','truth_E_GeV','pz','y_lepton','confirmed','label_physical','input_missing','fit_failure','wave_invalid','calo_invalid','negative_valid_raw','origin','origin_row']
    slim={k:d[k][active] for k in keep}
    # X-group boundaries from full outercal X only; never true energy or test quantiles.
    cfg=configuration();cal=d['role']==2
    for label,name in [('calo','ML_calo_total_E_EM_GeV'),('activity','SpacePoints')]:
        a=d['x'][:,cfg['features'].index(name)];edges=np.nanquantile(a[cal],[1/3,2/3]);slim['X_'+label]=np.where(np.isfinite(a[active]),np.digitize(a[active],edges),-1)
        save(OUT/f'X_{label}_groups.json',dict(feature=name,cal_edges=edges.tolist(),fit_on='outercal X only, no Y/prediction',missing_group=-1))
    np.savez_compressed(CACHE/'evaluation_input.npz',**slim)
    save(OUT/'worker_completion.json',dict(completed=True,new_fits=len(models),selected=selected,GPU=torch.cuda.get_device_name(),torch=torch.__version__,CUDA=torch.version.cuda,**resources(start)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare-protocol','qa','worker']);a=p.parse_args()
    if a.action=='prepare-protocol':prepare_protocol()
    else:globals()[a.action]()
