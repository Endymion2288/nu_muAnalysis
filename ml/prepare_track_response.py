#!/usr/bin/env python3
"""Join stage31 features without changing the frozen event support."""
import argparse,csv,json,time,resource
from pathlib import Path
import numpy as np
from track_response import configuration,profile
from train_bdt import write_table


def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args()
    repo=a.repo;cfg=configuration(repo);tick=time.perf_counter();cpu=time.process_time()
    root=repo/'ntuples/energy_ml_stage31';out=repo/'workbook/stage31_energy_ml'
    rows=[r for r in csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t') if r['partition'] in cfg['partitions']]
    shards=[];reports=[];resources=[]
    for batch in range((len(rows)+cfg['batch_size']-1)//cfg['batch_size']):
        with np.load(root/f'shards/{batch}.npz') as z:
            meta=json.loads(str(z['metadata_json']));assert meta['cfg']==cfg
            reports+=meta['reports'];resources.append({k:meta[k] for k in ['wall_s','cpu_s','peak_rss_MiB']})
            shards.append({k:z[k] for k in z.files if k!='metadata_json'})
    assert sorted(r['index'] for r in reports)==sorted(int(r['index']) for r in rows)
    full={k:np.concatenate([s[k] for s in shards]) for k in shards[0]}
    keys=list(zip(full['run'],full['eventID']));assert len(set(keys))==len(keys)
    lookup={key:i for i,key in enumerate(keys)};summary={};profiles=[]
    for part in cfg['partitions']:
        with np.load(repo/f'ntuples/energy_ml_stage12/dataset/{part}.npz') as z:
            idx=np.array([lookup[key] for key in zip(z['run'],z['eventID'])]);data={k:v[idx] for k,v in full.items()}
            for k in ['run','eventID','manifest_index']:np.testing.assert_array_equal(data[k],z[k])
            np.testing.assert_array_equal(data['reco_p_GeV'],z['ML_mu_p_GeV'])
            np.testing.assert_array_equal(data['reco_charge'],z['LeadTrack_charge'])
        np.savez_compressed(root/f'{part}_tracks.npz',**data,config_json=np.array(json.dumps(cfg)))
        with np.load(root/f'{part}_tracks.npz') as check:
            for k,v in data.items():np.testing.assert_array_equal(v,check[k])
        prof=profile(data,cfg['features']);profiles += [dict(partition=part,**r) for r in prof]
        summary[part]=dict(N=len(idx),backward=int((~data['lead_isForward']).sum()),
                           all_19_finite=int(np.isfinite(np.column_stack([data[k] for k in cfg['features']])).all(1).sum()))
    write_table(out/'feature_profile.tsv',profiles);write_table(out/'extraction_files.tsv',reports)
    write_table(out/'extraction_jobs.tsv',resources)
    summary.update(files=len(rows),input_events=sum(r['input_events'] for r in reports),
                   extraction_wall_s=sum(r['wall_s'] for r in resources),extraction_cpu_s=sum(r['cpu_s'] for r in resources),
                   extraction_peak_rss_MiB=max(r['peak_rss_MiB'] for r in resources),
                   consolidation_wall_s=time.perf_counter()-tick,consolidation_cpu_s=time.process_time()-cpu,
                   consolidation_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                   cache_bytes=sum((root/f'{p}_tracks.npz').stat().st_size for p in cfg['partitions']),readback_verified=True)
    (out/'extraction_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
