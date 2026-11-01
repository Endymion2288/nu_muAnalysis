#!/usr/bin/env python3
"""Read unchanged stage44 local features on frozen source-external identities."""
import argparse
import json
import resource
import time
from pathlib import Path
import awkward as ak
import numpy as np
import uproot
from local_activity import axes,summary,TRACKS
from calonu_inputs import manifest


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--index',type=int,required=True);p.add_argument('--pilot',action='store_true');a=p.parse_args(argv)
    repo=Path(__file__).resolve().parents[1];cfg=json.loads((repo/'ml/configs/source_transfer.json').read_text())
    local_cfg=json.loads((repo/'ml/configs/local_activity.json').read_text());tick,cpu=time.perf_counter(),time.process_time()
    with np.load(repo/'ntuples/energy_ml_stage48/selection.npz') as z:
        take=z['manifest_index']==a.index;d={k:z[k][take] for k in z.files}
    if a.pilot:d={k:v[:20] for k,v in d.items()}
    assert len(d['cache_row']) and a.index in cfg['indices']
    path=repo/'ntuples/energy_ml_stage48'/('pilot' if a.pilot else 'shards')/f'{a.index}.npz'
    assert not path.exists(),'Do not silently repeat successful extraction'
    raw_path=manifest(repo)[a.index]['input'];columns=['run','eventID','SpacePoints']+['SpacePoint_'+k for k in 'xyz']+['Track_'+n for n in TRACKS]
    with uproot.open(raw_path) as source:
        t=source['nt'];keys=t.arrays(['run','eventID'],library='np');lookup={int(e):j for j,e in enumerate(keys['eventID'])}
        assert len(lookup)==len(keys['eventID'])
        entries=np.array([lookup[int(e)] for e in d['eventID']]);np.testing.assert_array_equal(keys['run'][entries],d['run'])
        lo,hi=int(entries.min()),int(entries.max())+1
        arr=t.arrays(columns,entry_start=lo,entry_stop=hi)[entries-lo]
        bytes_read=int(source.file.source.num_requested_bytes);raw_entries=t.num_entries
    for k in ['run','eventID']:np.testing.assert_array_equal(ak.to_numpy(arr[k]),d[k])
    ax,rz,raw,lead=axes(arr,local_cfg)
    np.testing.assert_array_equal(raw['p0']/1000,d['expected_p_GeV'])
    for j,key in enumerate(['x0','y0','z0']):np.testing.assert_allclose(raw[key],d['expected_mu_xyz_mm'][:,j],rtol=2e-7,atol=1e-5,equal_nan=True)
    local=[];sp_max_layer=0.;points_N=0;nonfinite_points=0;max_dz=0.
    for i,row in enumerate(ak.to_list(arr)):
        points=np.column_stack([row['SpacePoint_'+k] for k in 'xyz']).astype(float)
        assert len(points)==row['SpacePoints']==d['expected_SpacePoints'][i]
        points_N+=len(points);nonfinite_points+=int((~np.isfinite(points).all(axis=1)).sum())
        z=points[:,2];good=np.isfinite(z);dist=abs(z[:,None]-np.array(local_cfg['station_centers_mm']))
        st=np.argmin(np.where(np.isfinite(dist),dist,np.inf),axis=1)
        ld=np.min(abs(z[good,None]-np.array(local_cfg['station_centers_mm'])[st[good],None]-np.array(local_cfg['layer_offsets_mm'])),axis=1)
        if len(ld):sp_max_layer=max(sp_max_layer,float(ld.max()));assert (ld<=local_cfg['layer_tolerance_mm']).all()
        for j,s in enumerate(local_cfg['local_stations']):
            m=good&(st==s)
            if m.any() and np.isfinite(ax[i,j]).all():
                dz=float(np.max(abs(z[m]-rz[i,j])));max_dz=max(max_dz,dz);assert dz<=local_cfg['maximum_local_dz_mm']
        values=summary(points,ax[i],local_cfg);assert values[:4].sum()==good.sum();local.append(values)
        shape=[]
        for coord in [0,1]:
            v=points[:,coord];mean=v.mean() if len(v) else np.nan
            shape.extend([mean,np.sqrt(np.maximum(0.,np.mean(v*v)-mean*mean)) if len(v) else np.nan])
        np.testing.assert_allclose(shape,d['expected_sp_shape_mm'][i],rtol=3e-6,atol=2e-5,equal_nan=True)
    values=np.stack(local);assert values.shape==(len(entries),22)
    md=dict(stage=48,index=a.index,pilot=a.pilot,input=raw_path,N=len(entries),source_N=1,raw_entries=raw_entries,
            entry_range=[lo,hi],decoded_entries=hi-lo,columns=columns,bytes_read=bytes_read,
            wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
            lead_index_nonzero_N=int((lead!=0).sum()),nonfinite_points=nonfinite_points,points_N=points_N,
            max_layer_distance_mm=sp_max_layer,max_local_dz_mm=max_dz,axis_missing_N=(~np.isfinite(ax).all(axis=2)).sum(axis=0).tolist(),
            original_F6_fingerprint_verified=True,feature_definition='exact stage44 axes/summary, unchanged config',identity_failures=0)
    path.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path,cache_row=d['cache_row'],run=d['run'],eventID=d['eventID'],local=values,metadata_json=np.array(json.dumps(md)))
    print(json.dumps(md),flush=True)


if __name__=='__main__':main()
