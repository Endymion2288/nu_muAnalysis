"""Stage106 ragged full-point model; no event/edge truncation or truth features."""
import functools
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from stage106_geometry import ROOT, OUT, CACHE, SEED, arrays, planes, canonical, local_edges, target_counts
from stage105_point_feasibility import CENTERS, OFFSETS


def hidden_plane(key,epoch):
    return int(np.random.default_rng(np.random.SeedSequence([SEED,int(epoch),int(key)])).integers(3,12))


def point_features(xyz,plane):
    return np.column_stack([np.arcsinh(xyz[:,:2]/100),np.eye(4)[plane//3],np.eye(3)[plane%3],
        (xyz[:,2]-CENTERS[plane//3]-OFFSETS[plane%3])/10]).astype('float32')


def event_from_xyz(xyz,available=True,hide=None):
    xyz=np.asarray(xyz,dtype=float)
    if not available:
        return dict(x=np.empty((0,10),np.float32),plane=np.empty(0,np.int64),
                    edges=np.empty((0,2),np.int64),ef=np.empty((0,4),np.float32),
                    meta=np.zeros(26,np.float32),target=np.zeros(257,np.float32))
    plane,_=planes(xyz)
    if np.any(plane<0):
        return event_from_xyz(xyz,False,hide)
    target=target_counts(xyz[plane==hide]).astype('float32') if hide is not None else np.zeros(257,np.float32)
    if hide is not None:
        xyz=xyz[plane!=hide];plane=plane[plane!=hide]
    xyz,plane=canonical(xyz,plane)
    edges=local_edges(xyz,plane)
    delta=xyz[edges[:,1]]-xyz[edges[:,0]]
    ef=np.column_stack([np.arcsinh(delta[:,:2]/100),delta[:,2]/31.5,np.log1p(np.linalg.norm(delta[:,:2],axis=1)/100)]).astype('float32')
    count=np.bincount(plane,minlength=12)
    meta=np.r_[np.log1p(count),count>0,1,len(xyz)==0].astype('float32')
    return dict(x=point_features(xyz,plane),plane=plane.astype(np.int64),edges=edges,ef=ef,meta=meta,target=target)


class PointData:
    def __init__(self,coordinate,summary,key):
        self.c=coordinate;self.summary=summary;self.key=key
        self.memo={};self.target_memo={}

    def get(self,i,epoch=None):
        i=int(i)
        if i not in self.memo:
            a,b=self.c['offsets'][i:i+2]
            self.memo[i]=event_from_xyz(self.c['xyz'][a:b],bool(self.c['available'][i]))
        original=self.memo[i]
        if epoch is None:
            return original
        hide=hidden_plane(self.key[i],epoch)
        # Masking a whole nominal plane does not create new adjacent-layer pairs.
        # Filter before visible pooling; no hidden-derived feature survives.
        p=original['plane'];take=p!=hide
        remap=np.cumsum(take)-1
        e=original['edges'];keep=take[e].all(1)
        x=original['x'][take];vp=p[take]
        count=np.bincount(vp,minlength=12)
        meta=np.r_[np.log1p(count),count>0,bool(self.c['available'][i]),bool(self.c['available'][i]) and len(x)==0].astype('float32')
        a,b=self.c['offsets'][i:i+2]
        rawxyz=self.c['xyz'][a:b]
        token=(i,hide)
        if token not in self.target_memo:
            self.target_memo[token]=target_counts(rawxyz[p==hide]).astype('float32') if self.c['available'][i] else np.zeros(257,np.float32)
        target=self.target_memo[token]
        return dict(x=x,plane=vp,edges=remap[e[keep]],ef=original['ef'][keep],meta=meta,target=target,hidden=hide)

    def microbatches(self,indices,epoch=None):
        group=[];nodes=edges=0
        for i in indices:
            v=self.get(i,epoch);n=len(v['x']);e=len(v['edges'])
            if group and (nodes+n>16384 or edges+e>262144):
                yield group
                group=[];nodes=edges=0
            group.append((int(i),v));nodes+=n;edges+=e
        if group:
            yield group

    def pack(self,group,device,pretrain=False):
        nodes=[];edges=[];ef=[];pool=[];metas=[];offset=0;ids=[];target=[];hidden=[]
        for event,(i,v) in enumerate(group):
            ids.append(i);nodes.append(v['x']);edges.append(v['edges']+offset);ef.append(v['ef'])
            pool.append(event*12+v['plane']);offset+=len(v['x']);metas.append(v['meta'])
            if pretrain:target.append(v['target']);hidden.append(v['hidden'])
        def tensor(x,dtype=torch.float32):return torch.as_tensor(x,dtype=dtype,device=device)
        edge=np.concatenate(edges)
        x=dict(x=tensor(np.concatenate(nodes)),edges=tensor(edge.T,torch.int64),ef=tensor(np.concatenate(ef)),
               pool=tensor(np.concatenate(pool),torch.int64),meta=tensor(np.stack(metas)),N=len(group))
        if pretrain:
            x.update(hidden=tensor(np.eye(12)[hidden]),target=tensor(np.stack(target)))
        else:
            x['summary']=tensor(self.summary[ids])
        return np.asarray(ids),x


class PointModel(nn.Module):
    def __init__(self,cell='B',center=6.):
        super().__init__();self.cell=cell
        self.point=nn.Sequential(nn.Linear(10,32),nn.SiLU(),nn.Linear(32,32),nn.SiLU())
        self.message=nn.Sequential(nn.Linear(68,32),nn.SiLU(),nn.Linear(32,32),nn.SiLU())
        self.update=nn.Sequential(nn.Linear(64,32),nn.SiLU(),nn.Linear(32,32))
        self.body=nn.Sequential(nn.Linear(537,64),nn.SiLU(),nn.Linear(64,64),nn.SiLU())
        self.head=nn.Linear(64,1)
        nn.init.zeros_(self.head.weight);nn.init.constant_(self.head.bias,center)
        self.decoder=nn.Sequential(nn.Linear(422,64),nn.SiLU(),nn.Linear(64,257))

    def encode(self,x,edges,ef,pool,meta,N):
        h=self.point(x)
        for _ in range(2):
            if self.cell=='A':
                m=self.message(x.new_zeros((1,68))).expand(len(h),-1)
            else:
                dest,source=edges
                m=h.new_zeros((len(h),32))
                if edges.shape[1]:
                    value=self.message(torch.cat([h[dest],h[source],ef],1))
                    m.index_add_(0,dest,value)
                    degree=torch.bincount(dest,minlength=len(h)).clamp_min(1)
                    m=m/degree[:,None]
            h=h+self.update(torch.cat([h,m],1))
        pooled=h.new_zeros((N*12,32))
        pooled.index_add_(0,pool,h)
        count=torch.bincount(pool,minlength=N*12).clamp_min(1)
        pooled=(pooled/count[:,None]).reshape(N,384)
        # Source-missing geometry has a zero embedding, distinct from an empty collection.
        return pooled*meta[:,24,None]

    def forward(self,x,edges,ef,pool,meta,N,summary=None,hidden=None,target=None):
        h=self.encode(x,edges,ef,pool,meta,N)
        if hidden is not None:
            return F.softplus(self.decoder(torch.cat([h,meta,hidden],1)))+1e-6
        return self.head(self.body(torch.cat([summary,h,meta],1))).squeeze(1)


def settings():
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False
    torch.backends.cudnn.allow_tf32=False


def initialized(cell,center=6.,device='cuda'):
    torch.manual_seed(SEED)
    model=PointModel(cell,center).to(device)
    return model


def predict(model,data,indices,device='cuda'):
    chunks=[]
    with torch.no_grad():
        for j in range(0,len(indices),256):
            for group in data.microbatches(indices[j:j+256]):
                ids,x=data.pack(group,device)
                chunks.append((ids,model(**x).cpu().numpy()))
    out=np.empty(len(data.key),np.float64)
    for ids,value in chunks:out[ids]=value
    return out
