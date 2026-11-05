"""Identical point inputs with ragged immutable values resident on CUDA.

Masking/gathering completes before model forward. Targets and scalar inputs are
separate; pretraining never transfers any scalar-summary tensor to the model.
"""
import numpy as np
import torch

from stage106_model import hidden_plane
from stage106_geometry import target_counts, planes


def ragged_indices(starts,counts):
    cumulative=np.r_[0,np.cumsum(counts)]
    return np.arange(cumulative[-1],dtype=np.int64)+np.repeat(starts-cumulative[:-1],counts)


class DevicePointData:
    def __init__(self,base,roles,device='cuda'):
        self.base=base;self.device=device;self.roles=np.asarray(roles)
        self.schedule={}
        values=[base.get(i) for i in range(len(base.key))]
        self.counts=np.array([len(v['x']) for v in values],np.int64)
        self.edgecounts=np.array([len(v['edges']) for v in values],np.int64)
        self.offsets=np.r_[0,np.cumsum(self.counts)]
        self.edgeoffsets=np.r_[0,np.cumsum(self.edgecounts)]
        self.plane_counts=np.stack([np.bincount(v['plane'],minlength=12) for v in values])
        self.incidence=np.stack([np.bincount(v['plane'][v['edges']].ravel(),minlength=12) for v in values])
        def tensor(value,dtype=None):return torch.as_tensor(value,dtype=dtype,device=device)
        self.x=tensor(np.concatenate([v['x'] for v in values]))
        self.plane=tensor(np.concatenate([v['plane'] for v in values]))
        self.edges=tensor(np.concatenate([v['edges']+offset for v,offset in zip(values,self.offsets[:-1])]))
        self.ef=tensor(np.concatenate([v['ef'] for v in values]))
        self.meta=tensor(np.stack([v['meta'] for v in values]))
        self.available=self.meta[:,24]
        self.node_starts=tensor(self.offsets[:-1])
        # NumPy log1p(float64 integer counts) then float32 matches reference exactly.
        maximum=int(self.plane_counts.max(initial=0))
        self.log_table=tensor(np.log1p(np.arange(maximum+1,dtype=np.int64)).astype('float32'))
        targets=np.zeros((len(values),9,257),np.float32)
        for i,v in enumerate(values):
            if self.roles[i]!=1 or not base.c['available'][i]:continue
            a,b=base.c['offsets'][i:i+2];xyz=base.c['xyz'][a:b]
            rawplane,_=planes(xyz)
            for h in range(3,12):targets[i,h-3]=target_counts(xyz[rawplane==h])
        self.targets=tensor(targets)

    def masks(self,epoch):
        if epoch not in self.schedule:
            self.schedule[epoch]=np.array([hidden_plane(k,epoch) for k in self.base.key],np.int64)
        return self.schedule[epoch]

    def prepare_schedules(self,epochs):
        for epoch in epochs:self.masks(epoch)

    def groups(self,indices,epoch=None,node_cap=16384,edge_cap=262144):
        indices=np.asarray(indices,dtype=np.int64)
        n=self.counts[indices].copy();e=self.edgecounts[indices].copy()
        if epoch is not None:
            h=self.masks(epoch)[indices]
            n-=self.plane_counts[indices,h];e-=self.incidence[indices,h]
        group=[];nodes=edges=0
        for i,ni,ei in zip(indices,n,e):
            if group and (nodes+ni>node_cap or edges+ei>edge_cap):
                yield np.array(group,np.int64)
                group=[];nodes=edges=0
            group.append(i);nodes+=ni;edges+=ei
        if group:yield np.array(group,np.int64)

    def pack(self,indices,epoch=None):
        ids=np.asarray(indices,dtype=np.int64);nc=self.counts[ids];ec=self.edgecounts[ids]
        ni=ragged_indices(self.offsets[ids],nc);ei=ragged_indices(self.edgeoffsets[ids],ec)
        def tensor(value,dtype=None):return torch.as_tensor(value,dtype=dtype,device=self.device)
        ti=tensor(ids);nidx=tensor(ni);eidx=tensor(ei)
        owner=torch.repeat_interleave(torch.arange(len(ids),device=self.device),tensor(nc),output_size=int(nc.sum()))
        eowner=torch.repeat_interleave(torch.arange(len(ids),device=self.device),tensor(ec),output_size=int(ec.sum()))
        local=tensor(np.r_[0,np.cumsum(nc)[:-1]])
        edges=self.edges[eidx]+(local-self.node_starts[ti])[eowner,None]
        x=self.x[nidx];plane=self.plane[nidx];ef=self.ef[eidx]
        pool=owner*12+plane
        result=dict(x=x,edges=edges.T,ef=ef,pool=pool,meta=self.meta[ti],N=len(ids))
        if epoch is None:
            result['summary']=tensor(self.base.summary[ids])
            return result,None
        hidden=tensor(self.masks(epoch)[ids])
        keep=plane!=hidden[owner]
        remap=keep.to(torch.int64).cumsum(0)-1
        edge_keep=keep[edges].all(1)
        visible_pool=pool[keep]
        counts=torch.bincount(visible_pool,minlength=len(ids)*12).reshape(len(ids),12)
        available=self.available[ti]
        meta=torch.cat([self.log_table[counts],(counts>0).to(torch.float32),available[:,None],
                        (available.bool()&(counts.sum(1)==0)).to(torch.float32)[:,None]],1)
        # Only visible tensors cross the model boundary; neither labels nor scalars.
        result=dict(x=x[keep],edges=remap[edges[edge_keep]].T,ef=ef[edge_keep],pool=visible_pool,
                    meta=meta,N=len(ids),hidden=torch.nn.functional.one_hot(hidden,num_classes=12).float())
        targets=self.targets[ti,hidden-3]
        return result,targets
