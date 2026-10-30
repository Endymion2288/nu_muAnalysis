"""Frozen scalar/point loading and efficient untruncated ragged batches."""
import csv
import json
from pathlib import Path

import numpy as np
import torch

from extract_spatial import feature_names
from train_bdt import check_features, load
from train_tabular import preprocess


class PointBatches:
    def __init__(self,points,counts,metadata,geometry,variant,seed,device='cuda'):
        centers=np.array(geometry['station_centers_mm']);layers=np.array(geometry['layer_offsets_mm'])
        self.counts=counts.sum(2).astype('int64');self.n=len(counts)
        self.starts=np.r_[0,self.counts.ravel().cumsum()[:-1]].reshape(-1,4)
        np.testing.assert_array_equal(metadata['offsets'],np.r_[0,self.counts.sum(1).cumsum()])
        xyz=np.array(points,copy=True);assert xyz.shape==(int(self.counts.sum()),3) and np.isfinite(xyz).all()
        station=abs(xyz[:,2,None]-centers).argmin(1)
        layer=abs((xyz[:,2]-centers[station])[:,None]-layers).argmin(1)
        # Check the canonical packing against the frozen 12 layer counts.
        expected=np.repeat(np.tile(np.arange(12),self.n),counts.reshape(-1))
        np.testing.assert_array_equal(station*3+layer,expected)
        if variant=='reassigned':
            for run,eid,begin,end in zip(metadata['run'],metadata['eventID'],metadata['offsets'][:-1],metadata['offsets'][1:]):
                rng=np.random.default_rng(np.random.SeedSequence([seed,int(run),int(eid)]))
                xy=xyz[begin:end,:2].copy();xyz[begin:end,:2]=xy[rng.permutation(end-begin)]
        features=np.zeros((len(xyz),10),dtype='float32');features[:,:2]=np.arcsinh(xyz[:,:2]/100.)
        if variant!='global':
            features[np.arange(len(xyz)),station+2]=1
            features[np.arange(len(xyz)),layer+6]=1
            features[:,9]=(xyz[:,2]-centers[station]-layers[layer])/10
        self.features=torch.as_tensor(features,device=device);self.device=device
        self.counts_gpu=torch.as_tensor(self.counts,device=device,dtype=torch.long)
        self.batch_points_max_seen=0

    def batch(self,ids):
        counts=self.counts[ids].reshape(-1);starts=self.starts[ids].reshape(-1)
        prefixes=np.r_[0,counts.cumsum()[:-1]];total=int(counts.sum())
        self.batch_points_max_seen=max(self.batch_points_max_seen,total)
        indices=np.repeat(starts-prefixes,counts)+np.arange(total)
        return self.features[torch.as_tensor(indices,device=self.device)],self.counts_gpu[torch.as_tensor(ids,device=self.device)]


def summary_values(spatial):
    counts=spatial['counts'].reshape(-1,4,3).astype(float);total=counts.sum(2)
    values=spatial['moments'].reshape(-1,4,5).astype(float)
    values[:,:,:4]=np.arcsinh(values[:,:,:4]/100.)
    values[:,:,4]=np.arcsinh(values[:,:,4]/10000.)
    fraction=counts/np.maximum(total[:,:,None],1)
    result=np.concatenate([np.nan_to_num(values),np.log1p(total)[:,:,None]/10.,fraction,(total==0)[:,:,None]],axis=2)
    assert result.shape[1:]==(4,10)
    return result.astype('float32')


def transform_scalar(raw,state):
    missing=~np.isfinite(raw)
    a=np.arcsinh(np.where(missing,np.nan,raw)/np.array(state['scale']))
    a=np.where(missing,np.array(state['fill']),a)
    return np.column_stack([(a-np.array(state['mean']))/np.array(state['std']),missing]).astype('float32')


def load_data(repo,cache,cfg,baseline,smoke=False,fixed_preprocessing=None):
    rows=list(csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t'))
    counts,moments=feature_names();original=sum([baseline['feature_groups'][g] for g in baseline['feature_versions']['F5']],[])
    names=original+counts+moments;check_features(names,original+counts+moments)
    parts=[]
    for part,limit in [('train',1200),('validation',400)]:
        base,groups=load(rows,baseline,part)
        with np.load(cache/f'ntuples/energy_ml_stage18/{part}.npz') as d:
            sp={k:d[k] for k in ['counts','moments','run','eventID']}
        with np.load(cache/f'ntuples/energy_ml_stage19/{part}_events.npz') as d:
            assert json.loads(str(d['config_json']))==cfg
            metadata={k:d[k] for k in ['run','eventID','manifest_index','offsets']}
        for key in ['run','eventID']:
            np.testing.assert_array_equal(base[key],sp[key]);np.testing.assert_array_equal(base[key],metadata[key])
        points=np.load(cache/f'ntuples/energy_ml_stage19/{part}_points.npy',mmap_mode='r')
        if smoke:
            base={k:v[:limit] for k,v in base.items()};groups=groups[:limit];sp={k:v[:limit] for k,v in sp.items()}
            metadata={k:v[:limit+1] if k=='offsets' else v[:limit] for k,v in metadata.items()};points=points[:metadata['offsets'][-1]]
        extra={name:sp['counts'][:,i] for i,name in enumerate(counts)}
        extra.update({name:sp['moments'][:,i] for i,name in enumerate(moments)})
        data=dict(**base,**extra)
        parts.append(dict(scalar=np.column_stack([data[k] for k in names]),summary=summary_values(sp),points=points,
                          counts=sp['counts'].reshape(-1,4,3),metadata=metadata,groups=groups,target=base[baseline['target']]))
    assert not set(parts[0]['groups'])&set(parts[1]['groups'])
    if fixed_preprocessing is None:
        a,b,state=preprocess(parts[0]['scalar'],parts[1]['scalar'])
        target=np.log(parts[0]['target']);center=float(target.mean());spread=float(target.std())
    else:
        assert names==fixed_preprocessing['features'];state=fixed_preprocessing['preprocessor']
        a,b=[transform_scalar(part['scalar'],state) for part in parts]
        center=fixed_preprocessing['target_center'];spread=fixed_preprocessing['target_spread']
    parts[0]['scalar']=a;parts[1]['scalar']=b
    for part in parts:
        part['y']=((np.log(part['target'])-center)/spread).astype('float32')
    return parts,dict(features=names,preprocessor=state,target_center=center,target_spread=spread)
