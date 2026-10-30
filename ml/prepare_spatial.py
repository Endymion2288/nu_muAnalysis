#!/usr/bin/env python3
"""Consolidate station summaries in frozen cache order and audit global moments."""
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np
import yaml

from train_bdt import write_table


def main():
    repo=Path(__file__).resolve().parents[1];tick=time.perf_counter();cpu=time.process_time()
    cfg=yaml.safe_load((repo/'ml/configs/spatial.yaml').read_text());root=repo/'ntuples/energy_ml_stage18'
    out=repo/'workbook/stage18_energy_ml'
    rows=[r for r in csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t') if r['partition'] in cfg['partitions']]
    shards=[];reports=[]
    for batch in range((len(rows)+11)//12):
        with np.load(root/f'shards/{batch}.npz') as d:
            assert json.loads(str(d['config_json']))==cfg
            reports+=json.loads(str(d['reports_json']));shards.append({k:d[k] for k in d.files if not k.endswith('_json')})
    assert sorted(r['index'] for r in reports)==sorted(int(r['index']) for r in rows)
    full={k:np.concatenate([d[k] for d in shards]) for k in shards[0]}
    keys=list(zip(full['run'],full['eventID']));assert len(set(keys))==len(keys)
    lookup={key:i for i,key in enumerate(keys)};parts={}
    for part in cfg['partitions']:
        with np.load(repo/f'ntuples/energy_ml_stage12/dataset/{part}.npz') as old:
            index=[lookup[key] for key in zip(old['run'],old['eventID'])];data={k:v[index] for k,v in full.items()}
            for k in ['run','eventID','manifest_index']:np.testing.assert_array_equal(data[k],old[k])
            np.testing.assert_array_equal(data['counts'].sum(axis=1),old['SpacePoints'])
            cols=['ML_sp_mean_x_mm','ML_sp_rms_x_mm','ML_sp_mean_y_mm','ML_sp_rms_y_mm']
            delta=data['global_moments']-np.column_stack([old[k] for k in cols])
            finite=np.isfinite(data['global_moments']);np.testing.assert_array_equal(finite,np.isfinite(np.column_stack([old[k] for k in cols])))
            if np.nanmax(abs(delta))>.02:raise RuntimeError('Global moments differ by >0.02 mm: investigate precision/ordering')
            # Reconstruct global first/second moments from station statistics.
            count=data['counts'].reshape(-1,4,3).sum(axis=2);total=count.sum(axis=1)
            for name in ['moments']+[f'reassigned_{i}' for i in range(3)]:
                m=data[name].reshape(-1,4,5)
                for coordinate,mean_col,rms_col in [(0,0,1),(1,2,3)]:
                    means=m[:,:,coordinate];rms=m[:,:,coordinate+2]
                    mean=np.nansum(count*means,axis=1)/total
                    variance=np.nansum(count*(rms**2+(means-mean[:,None])**2),axis=1)/total
                    np.testing.assert_allclose(mean,data['global_moments'][:,mean_col],atol=2e-5,rtol=1e-5)
                    np.testing.assert_allclose(np.sqrt(variance),data['global_moments'][:,rms_col],atol=2e-5,rtol=1e-5)
            parts[part]=dict(events=len(index),spacepoints=int(total.sum()),empty_stations=int((count==0).sum()),
                             maximum_global_moment_difference_mm=np.nanmax(abs(delta),axis=0).tolist(),station_points=count.sum(axis=0).tolist())
        np.savez_compressed(root/f'{part}.npz',**data,config_json=np.array(json.dumps(cfg)))
        with np.load(root/f'{part}.npz') as check:
            for k,v in data.items():np.testing.assert_array_equal(v,check[k])
    write_table(out/'extraction_files.tsv',reports)
    summary=dict(partitions=parts,files=len(reports),input_events=sum(r['input_events'] for r in reports),
                 selected_events=len(keys),spacepoints=sum(r['spacepoints'] for r in reports),
                 file_wall_sum_s=sum(r['wall_s'] for r in reports),file_cpu_sum_s=sum(r['cpu_s'] for r in reports),
                 extraction_peak_rss_MiB=max(r['peak_rss_MiB'] for r in reports),source_file_bytes=sum(r['source_file_bytes'] for r in reports),
                 maximum_layer_distance_mm=max(r['maximum_layer_distance_mm'] for r in reports),
                 layer_point_counts=np.sum([r['point_counts'] for r in reports],axis=0).tolist(),
                 final_cache_bytes=sum((root/f'{p}.npz').stat().st_size for p in cfg['partitions']),
                 null_global_moments_and_counts_verified=True,all_fields_readback_verified=True,
                 consolidation_wall_s=time.perf_counter()-tick,consolidation_cpu_s=time.process_time()-cpu,
                 consolidation_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'extraction_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
