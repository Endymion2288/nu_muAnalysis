#!/usr/bin/env python3
"""Extract frozen selected SpacePoint summaries; no labels or new selection."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot
import yaml


def feature_names():
    counts=[f'SP_s{s}_l{l}_count' for s in range(4) for l in range(3)]
    moments=[f'SP_s{s}_{v}' for s in range(4) for v in ['mean_x_mm','mean_y_mm','rms_x_mm','rms_y_mm','cov_xy_mm2']]
    return counts,moments


def moments(x,y,station,event,n):
    group=event*4+station
    count=np.bincount(group,minlength=n*4).reshape(n,4)
    def mean(v):
        total=np.bincount(group,weights=v,minlength=n*4).reshape(n,4)
        return np.divide(total,count,out=np.full((n,4),np.nan),where=count>0)
    mx,my=mean(x),mean(y)
    # Center before accumulating to avoid subtracting nearly equal large moments.
    dx=x-mx[event,station];dy=y-my[event,station]
    return np.stack([mx,my,np.sqrt(mean(dx*dx)),np.sqrt(mean(dy*dy)),mean(dx*dy)],axis=2).reshape(n,20)


def extract(row,selected,cfg,entry_stop=None):
    tick=time.perf_counter();cpu=time.process_time()
    wanted=selected['eventID'][selected['manifest_index']==int(row['index'])]
    collected=[];point_counts=np.zeros((4,3),dtype=np.int64);max_layer_distance=0.;ranges=[];raw=0
    with uproot.open(row['input']) as source:
        tree=source['nt'];file_bytes=Path(row['input']).stat().st_size
        branches=['run','eventID','SpacePoints','SpacePoint_x','SpacePoint_y','SpacePoint_z']
        for arrays in tree.iterate(branches,step_size='32 MB',entry_stop=entry_stop):
            raw+=len(arrays);a=arrays[np.isin(ak.to_numpy(arrays.eventID),wanted)]
            if not len(a):continue
            lengths=ak.to_numpy(ak.num(a.SpacePoint_x));n=len(a)
            assert np.array_equal(lengths,ak.to_numpy(ak.num(a.SpacePoint_y)))
            assert np.array_equal(lengths,ak.to_numpy(ak.num(a.SpacePoint_z)))
            np.testing.assert_array_equal(lengths,ak.to_numpy(a.SpacePoints))
            x,y,z=[ak.to_numpy(ak.flatten(a['SpacePoint_'+c])).astype(float) for c in 'xyz']
            assert np.isfinite(x).all() and np.isfinite(y).all() and np.isfinite(z).all()
            event=np.repeat(np.arange(n),lengths)
            centers=np.array(cfg['station_centers_mm']);offsets=np.array(cfg['layer_offsets_mm'])
            station=abs(z[:,None]-centers).argmin(axis=1)
            layer=abs((z-centers[station])[:,None]-offsets).argmin(axis=1)
            distance=abs(z-centers[station]-offsets[layer]);maximum=float(distance.max(initial=0))
            if maximum>cfg['maximum_layer_distance_mm']:raise RuntimeError(f'Unmapped geometry: {maximum} mm')
            max_layer_distance=max(max_layer_distance,maximum)
            count=np.bincount(event*12+station*3+layer,minlength=n*12).reshape(n,12)
            point_counts+=count.sum(axis=0).reshape(4,3)
            values=moments(x,y,station,event,n)
            null=[]
            for seed in cfg['seeds']:
                donor=np.arange(len(x));offset=0
                for eid,length in zip(ak.to_numpy(a.eventID),lengths):
                    rng=np.random.default_rng(np.random.SeedSequence([seed,int(row['run']),int(eid)]))
                    donor[offset:offset+length]=offset+rng.permutation(length);offset+=length
                # Pairwise xy and each event's multiset are exactly unchanged.
                null.append(moments(x[donor],y[donor],station,event,n))
            def global_mean(v):
                return np.divide(np.bincount(event,weights=v,minlength=n),lengths,out=np.full(n,np.nan),where=lengths>0)
            gx,gy=global_mean(x),global_mean(y)
            global_values=np.column_stack([gx,np.sqrt(global_mean((x-gx[event])**2)),gy,np.sqrt(global_mean((y-gy[event])**2))])
            result=dict(run=ak.to_numpy(a.run),eventID=ak.to_numpy(a.eventID),manifest_index=np.full(n,int(row['index']),dtype=np.int32),
                        counts=count.astype('int32'),moments=values.astype('float32'),global_moments=global_values)
            for i,v in enumerate(null):result[f'reassigned_{i}']=v.astype('float32')
            collected.append(result)
            ranges.append([[float(v.min()),float(v.max())] for v in [x,y,z]])
    if not collected:raise RuntimeError('No selected events')
    data={k:np.concatenate([a[k] for a in collected]) for k in collected[0]}
    order=np.argsort(data['eventID']);data={k:v[order] for k,v in data.items()}
    if entry_stop is None:np.testing.assert_array_equal(data['eventID'],np.sort(wanted))
    assert np.all(data['run']==int(row['run']))
    report=dict(index=int(row['index']),run=int(row['run']),partition=row['partition'],input=row['input'],
                input_events=raw,selected_events=len(order),spacepoints=int(point_counts.sum()),point_counts=point_counts.tolist(),
                maximum_layer_distance_mm=max_layer_distance,
                wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                source_file_bytes=file_bytes,alignment_failures=0)
    # Ranges need independent min/max across chunks.
    report['coordinate_ranges_mm']=[[min(r[c][0] for r in ranges),max(r[c][1] for r in ranges)] for c in range(3)]
    return data,report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--batch',type=int,default=0)
    p.add_argument('--index',type=int);p.add_argument('--entry-stop',type=int);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();cfg=yaml.safe_load((args.repo/'ml/configs/spatial.yaml').read_text())
    rows=[r for r in csv.DictReader((args.repo/'ml/configs/files.tsv').open(),delimiter='\t') if r['partition'] in cfg['partitions']]
    rows=[r for r in rows if int(r['index'])==args.index] if args.index is not None else rows[args.batch*12:(args.batch+1)*12]
    selected={}
    for part in cfg['partitions']:
        with np.load(Path(rows[0]['cache']).parents[1]/'dataset'/f'{part}.npz') as d:
            selected[part]={k:d[k] for k in ['run','eventID','manifest_index']}
    data=[];reports=[]
    for row in rows:
        d,r=extract(row,selected[row['partition']],cfg,args.entry_stop);data.append(d);reports.append(r);print(json.dumps(r),flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(args.output,**{k:np.concatenate([d[k] for d in data]) for k in data[0]},
                        reports_json=np.array(json.dumps(reports)),config_json=np.array(json.dumps(cfg)))


if __name__=='__main__':main()
