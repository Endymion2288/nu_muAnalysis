#!/usr/bin/env python3
"""Join compact truth diagnostics to frozen development IDs, with readback QA."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np
import yaml

from train_bdt import write_table


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    args=p.parse_args(); repo=args.repo; tick=time.perf_counter(); cpu=time.process_time()
    cfg=yaml.safe_load((repo/'ml/configs/physics_decomposition.yaml').read_text())
    root=repo/'ntuples/energy_ml_stage15'; report=repo/'workbook/stage15_energy_ml'
    rows=[r for r in csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t') if r['partition'] in cfg['partitions']]
    shards=[]; reports=[]
    for batch in range((len(rows)+11)//12):
        with np.load(root/f'shards/{batch}.npz') as d:
            if json.loads(str(d['config_json']))!=cfg:raise RuntimeError('Extraction config mismatch')
            reports+=json.loads(str(d['reports_json']))
            shards.append({k:d[k] for k in d.files if not k.endswith('_json')})
    if sorted(r['index'] for r in reports)!=sorted(int(r['index']) for r in rows):
        raise RuntimeError('Missing/duplicate manifest inputs')
    full={k:np.concatenate([s[k] for s in shards]) for k in shards[0]}
    keys=list(zip(full['run'],full['eventID']))
    if len(set(keys))!=len(keys):raise RuntimeError('Duplicate run/eventID')
    lookup={key:i for i,key in enumerate(keys)}
    summary={}
    for part in cfg['partitions']:
        with np.load(repo/f'ntuples/energy_ml_stage12/dataset/{part}.npz') as old:
            index=np.array([lookup[(r,e)] for r,e in zip(old['run'],old['eventID'])])
            data={k:v[index] for k,v in full.items()}
            for k in ['run','eventID','manifest_index']:np.testing.assert_array_equal(data[k],old[k])
            np.testing.assert_allclose(data['truth_E_GeV'],old['ML_truth_E_GeV'],rtol=1e-12,atol=1e-10)
            np.testing.assert_allclose(data['reco_p_GeV'],old['ML_mu_p_GeV'],rtol=1e-12,atol=1e-10)
            for c in ['x','y','z']:np.testing.assert_array_equal(data[f'vertex_{c}_mm'],old[f'truth_dec_{c}_nu'])
        np.savez_compressed(root/f'{part}_truth.npz',**data,config_json=np.array(json.dumps(cfg)))
        with np.load(root/f'{part}_truth.npz') as check:
            for k,v in data.items():np.testing.assert_array_equal(v,check[k])
        summary[part]=dict(events=len(index),unique_primary=int(data['primary_valid'].sum()),
                           lead_primary_parent_confirmed=int(data['lead_primary_parent_confirmed'].sum()),
                           any_primary_parent_confirmed=int(data['any_primary_parent_confirmed'].sum()),
                           station1_available=int(data['primary_st1_valid'].sum()))
    write_table(report/'extraction_files.tsv',reports)
    summary.update(files=len(rows),input_events=sum(r['input_events'] for r in reports),
                   selected_events=len(keys),file_read_wall_s=sum(r['wall_s'] for r in reports),
                   extraction_peak_rss_MiB=max(r['peak_rss_MiB'] for r in reports),
                   consolidation_wall_s=time.perf_counter()-tick,consolidation_cpu_s=time.process_time()-cpu,
                   consolidation_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                   final_cache_bytes=sum((root/f'{part}_truth.npz').stat().st_size for part in cfg['partitions']),
                   all_fields_readback_verified=True)
    (report/'extraction_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
