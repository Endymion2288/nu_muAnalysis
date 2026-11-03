"""Stage69 matched log-energy regressors with optional truth-transfer supervision."""
import json
import time
import numpy as np
import torch
from torch import nn
from audited_features import REPO, configuration, load
from continuous_response import transform, transform_state
from group_risk import training_split, LOW, COST
from expert_combination import begin, resources, save, masks

OUT=REPO/'workbook/stage69_energy_ml'
ART=REPO/'ml/artifacts/stage69'


def inputs():
    d,s,x=load();rows=s['row'];role=np.full(len(rows),'unused',dtype='<U6')
    role[d['train_eligible'][rows]]='train';role[d['cal_eligible'][rows]]='cal';role[d['partition'][rows]=='validation']='eval'
    use=role!='unused';row=rows[use]
    out={k:d[k][row] for k in ['truth_E_GeV','y_lepton','confirmed','source','group','component','incoming','primary_valid','primary_candidates','primary_p_GeV']}
    out.update(row=row,role=role[use],x=x[use],pz=d['reco_pz_GeV'][row],missing=np.isnan(x[use]).any(axis=1))
    assert [int((out['role']==r).sum()) for r in ['train','cal','eval']]==[41447,8440,14057]
    return out


def labels(d):
    y=d['y_lepton'];valid=d['confirmed']&np.isfinite(y)&(y>=0)&(y<=1)
    target=np.full(len(y),-1,dtype=np.int64)
    target[valid]=np.searchsorted([.2,.8],y[valid],side='right')
    return target,valid


class Network(nn.Module):
    def __init__(self,dim):
        super().__init__()
        self.shared=nn.Sequential(nn.Linear(dim,64),nn.SiLU(),nn.Linear(64,64),nn.SiLU())
        self.regression=nn.Linear(64,1);self.auxiliary=nn.Linear(64,3)
        # Both families begin at the fold's mean log-energy, with identical weights.
        nn.init.zeros_(self.regression.weight);nn.init.zeros_(self.regression.bias)

    def forward(self,x):
        h=self.shared(x)
        return self.regression(h).ravel(),self.auxiliary(h)


def objective(pred,logits,target,classes,valid,auxiliary_weight,valid_fraction):
    mse=torch.mean((pred-target)**2)
    if auxiliary_weight and bool(valid.any()):
        ce=nn.functional.cross_entropy(logits[valid],classes[valid],reduction='sum')/(len(target)*valid_fraction)
    else:ce=pred.sum()*0.
    return mse+auxiliary_weight*ce,mse,ce


def predict(model,x,state,target_center,batch=4096):
    """Deployment takes only the audited readout matrix and training-only state."""
    xx,_=transform(x,state);points=[];prob=[];model.eval()
    with torch.inference_mode():
        for start in range(0,len(xx),batch):
            pred,logits=model(torch.from_numpy(xx[start:start+batch]))
            points.append(pred.numpy().astype(float)+target_center)
            prob.append(torch.softmax(logits,dim=1).numpy())
    return np.concatenate(points),np.concatenate(prob)


def fit_one(x,y,classes,valid,state,p,family,destination,epochs=None):
    torch.set_num_threads(p['cpu_threads']);torch.use_deterministic_algorithms(True);torch.manual_seed(p['seed'])
    xx,_=transform(x,state);xx=torch.from_numpy(xx)
    center=float(y.mean());yy=torch.from_numpy((y-center).astype('float32'))
    cc=torch.from_numpy(classes);vv=torch.from_numpy(valid);fraction=float(valid.mean());assert fraction>0
    model=Network(xx.shape[1]);initial={k:v.detach().clone() for k,v in model.state_dict().items()}
    optimizer=torch.optim.AdamW(model.parameters(),lr=p['learning_rate'],weight_decay=p['weight_decay'])
    order_rng=torch.Generator().manual_seed(p['seed']+1);weight=0. if family=='C' else p['auxiliary_weight']
    epochs=p['epochs'] if epochs is None else epochs;history=[];start=begin()
    for epoch in range(epochs):
        model.train();order=torch.randperm(len(xx),generator=order_rng);mse_sum=ce_sum=0.
        for idx in order.split(p['batch_size']):
            optimizer.zero_grad(set_to_none=True);pred,logits=model(xx[idx])
            loss,mse,ce=objective(pred,logits,yy[idx],cc[idx],vv[idx],weight,fraction)
            assert torch.isfinite(loss)
            loss.backward();optimizer.step();mse_sum+=float(mse.detach())*len(idx);ce_sum+=float(ce.detach())*len(idx)
        history.append(dict(epoch=epoch+1,online_main_MSE=mse_sum/len(xx),online_aux_CE=ce_sum/len(xx),elapsed_wall_s=time.perf_counter()-start[0]))
        if epoch%20==19:print(family,history[-1],flush=True)
        assert time.perf_counter()-start[0]<p['pair_wall_budget_s'] and time.process_time()-start[1]<p['pair_cpu_budget_s']
    measured=resources(start);destination.mkdir(parents=True,exist_ok=True)
    torch.save(dict(state_dict=model.state_dict(),input_dim=xx.shape[1],feature_state=state,target_center=center,family=family,seed=p['seed'],epochs=epochs,features=configuration()['features']),destination/(family+'.pt'))
    point,prob=predict(model,x.numpy() if isinstance(x,torch.Tensor) else x,state,center)
    train_mse=float(np.mean((point-y)**2));ce=float(-np.log(np.maximum(prob[np.arange(len(prob))[valid],classes[valid]],np.finfo(np.float32).tiny)).mean())
    return model,initial,dict(family=family,epochs=epochs,train_N=len(y),auxiliary_valid_N=int(valid.sum()),parameter_count=sum(v.numel() for v in model.parameters()),target_center=center,resources=measured,terminal_train_MSE=train_mse,terminal_aux_CE=ce,history=history)


def restore(path):
    data=torch.load(path,map_location='cpu',weights_only=False)
    model=Network(data['input_dim']);model.load_state_dict(data['state_dict']);model.eval()
    return model,data
