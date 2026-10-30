#!/usr/bin/env python3
"""Retain every selected SpacePoint, packed by event/station/layer."""
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


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--batch',type=int,default=0);p.add_argument('--index',type=int);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();repo=args.repo
    cfg=yaml.safe_load((repo/'ml/configs/sets.yaml').read_text());geo=yaml.safe_load((repo/cfg['geometry_config']).read_text())
    rows=[r for r in csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t') if r['partition'] in cfg['partitions']]
    rows=[r for r in rows if int(r['index'])==args.index] if args.index is not None else rows[args.batch*12:(args.batch+1)*12]
    selected={}
    for part in cfg['partitions']:
        with np.load(Path(rows[0]['cache']).parents[1]/'dataset'/f'{part}.npz') as d:selected[part]={k:d[k] for k in ['eventID','manifest_index']}
    events=[];reports=[]
    centers=np.array(geo['station_centers_mm']);offsets=np.array(geo['layer_offsets_mm'])
    for row in rows:
        tick=time.perf_counter();cpu=time.process_time();s=selected[row['partition']]
        wanted=s['eventID'][s['manifest_index']==int(row['index'])];found=[];points_total=0;raw=0;max_distance=0.;max_loss=0.
        with uproot.open(row['input']) as source:
            for a in source['nt'].iterate(['run','eventID','SpacePoints','SpacePoint_x','SpacePoint_y','SpacePoint_z'],step_size='32 MB'):
                raw+=len(a);a=a[np.isin(ak.to_numpy(a.eventID),wanted)]
                for event in a:
                    xyz=np.column_stack([ak.to_numpy(event['SpacePoint_'+axis]) for axis in 'xyz'])
                    assert len(xyz)==int(event.SpacePoints) and np.isfinite(xyz).all()
                    station=abs(xyz[:,2,None]-centers).argmin(1)
                    layer=abs((xyz[:,2]-centers[station])[:,None]-offsets).argmin(1)
                    distance=abs(xyz[:,2]-centers[station]-offsets[layer]);max_distance=max(max_distance,float(distance.max(initial=0)))
                    if max_distance>geo['maximum_layer_distance_mm']:raise RuntimeError('Point outside verified geometry')
                    xyz=xyz[np.argsort(station*3+layer,kind='stable')]
                    packed=xyz.astype('float32');max_loss=max(max_loss,float(abs(packed.astype(float)-xyz).max(initial=0)))
                    key=(int(event.run),int(event.eventID),int(row['index']))
                    assert key[0]==int(row['run']);events.append((key,packed));found.append(key[1]);points_total+=len(xyz)
        np.testing.assert_array_equal(np.sort(found),np.sort(wanted))
        report=dict(index=int(row['index']),run=int(row['run']),partition=row['partition'],input=row['input'],
                    input_events=raw,selected_events=len(found),points=points_total,maximum_layer_distance_mm=max_distance,
                    maximum_float32_coordinate_loss_mm=max_loss,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                    peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,source_file_bytes=Path(row['input']).stat().st_size)
        reports.append(report);print(json.dumps(report),flush=True)
    keys=np.array([e[0] for e in events],dtype='int64');lengths=np.array([len(e[1]) for e in events],dtype='int64')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(args.output,run=keys[:,0],eventID=keys[:,1],manifest_index=keys[:,2],offsets=np.r_[0,lengths.cumsum()],
                        points=np.concatenate([e[1] for e in events]),reports_json=np.array(json.dumps(reports)),config_json=np.array(json.dumps(cfg)))


if __name__=='__main__':main()
