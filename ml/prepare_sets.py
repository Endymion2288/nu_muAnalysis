#!/usr/bin/env python3
"""Consolidate full point caches in frozen event order, auditing every station."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np
import yaml

from extract_spatial import moments
from train_bdt import write_table


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--cache-root',type=Path);p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args();repo=args.repo;cache=args.cache_root or repo;out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    tick=time.perf_counter();cpu=time.process_time();cfg=yaml.safe_load((repo/'ml/configs/sets.yaml').read_text())
    geo=yaml.safe_load((repo/cfg['geometry_config']).read_text());centers=np.array(geo['station_centers_mm']);offsets=np.array(geo['layer_offsets_mm'])
    rows=[r for r in csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t') if r['partition'] in cfg['partitions']]
    files=[];lookup={};dest={};metadata={};old_spatial={};max_moment_difference=np.zeros(5)
    for part in cfg['partitions']:
        with np.load(cache/f'ntuples/energy_ml_stage18/{part}.npz') as d:
            old_spatial[part]={k:d[k] for k in ['run','eventID','manifest_index','counts','moments','global_moments']}
        d=old_spatial[part];lengths=d['counts'].sum(1);starts=np.r_[0,lengths.cumsum()]
        metadata[part]=dict(run=d['run'],eventID=d['eventID'],manifest_index=d['manifest_index'],offsets=starts)
        dest[part]=np.lib.format.open_memmap(out/f'{part}_points.npy',mode='w+',dtype='float32',shape=(int(starts[-1]),3))
        for i,key in enumerate(zip(d['run'],d['eventID'])):
            if key in lookup:raise RuntimeError('Duplicate frozen event')
            lookup[key]=(part,i,int(starts[i]),int(starts[i+1]));
    seen=set()
    for batch in range((len(rows)+11)//12):
        with np.load(cache/f'ntuples/energy_ml_stage19/shards/{batch}.npz') as d:
            assert json.loads(str(d['config_json']))==cfg
            files+=json.loads(str(d['reports_json']));points=d['points'];starts=d['offsets'];keys=list(zip(d['run'],d['eventID']))
            lengths=np.diff(starts);n=len(keys);event=np.repeat(np.arange(n),lengths)
            station=abs(points[:,2,None]-centers).argmin(1);layer=abs((points[:,2]-centers[station])[:,None]-offsets).argmin(1)
            counts=np.bincount(event*12+station*3+layer,minlength=n*12).reshape(n,12)
            computed=moments(points[:,0].astype(float),points[:,1].astype(float),station,event,n)
            expected=[]
            for i,key in enumerate(keys):
                assert key not in seen;seen.add(key);part,j,begin,end=lookup[key]
                assert int(d['manifest_index'][i])==int(old_spatial[part]['manifest_index'][j])
                np.testing.assert_array_equal(counts[i],old_spatial[part]['counts'][j]);assert end-begin==lengths[i]
                dest[part][begin:end]=points[starts[i]:starts[i+1]]
                np.testing.assert_array_equal(dest[part][begin:end],points[starts[i]:starts[i+1]])
                expected.append(old_spatial[part]['moments'][j])
            expected=np.array(expected);np.testing.assert_allclose(computed,expected,atol=2e-5,rtol=1e-5)
            max_moment_difference=np.maximum(max_moment_difference,np.nanmax(abs(computed-expected).reshape(-1,4,5),axis=(0,1)))
    assert seen==set(lookup) and sorted(r['index'] for r in files)==sorted(int(r['index']) for r in rows)
    for part in cfg['partitions']:
        dest[part].flush()
        np.savez_compressed(out/f'{part}_events.npz',**metadata[part],config_json=np.array(json.dumps(cfg)))
    write_table(out/'extraction_files.tsv',files)
    summary=dict(files=len(files),events=len(seen),points=sum(r['points'] for r in files),input_events=sum(r['input_events'] for r in files),
                 file_wall_sum_s=sum(r['wall_s'] for r in files),file_cpu_sum_s=sum(r['cpu_s'] for r in files),
                 extraction_peak_rss_MiB=max(r['peak_rss_MiB'] for r in files),source_file_bytes=sum(r['source_file_bytes'] for r in files),
                 maximum_float32_coordinate_loss_mm=max(r['maximum_float32_coordinate_loss_mm'] for r in files),
                 maximum_station_moment_difference=dict(zip(['mean_x_mm','mean_y_mm','rms_x_mm','rms_y_mm','cov_xy_mm2'],max_moment_difference.tolist())),
                 all_event_keys_counts_and_moments_verified=True,
                 parts={part:dict(events=len(metadata[part]['run']),points=int(metadata[part]['offsets'][-1])) for part in cfg['partitions']},
                 final_cache_bytes=sum((out/f'{part}_{kind}').stat().st_size for part in cfg['partitions'] for kind in ['points.npy','events.npz']),
                 wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'extraction_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
