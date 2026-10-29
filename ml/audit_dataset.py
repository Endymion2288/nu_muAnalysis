#!/usr/bin/env python3
"""Verify all extraction shards, consolidate five partitions, write aggregate QA."""
import argparse
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path

import numpy as np
import yaml

def write_table(path, rows):
    with path.open('w') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--remove-shards',action='store_true')
    args=p.parse_args();repo=args.repo.resolve();args.output_dir.mkdir(parents=True,exist_ok=True)
    cfg=yaml.safe_load((repo/'ml/configs/baseline.yaml').read_text())
    rows=list(csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t'))
    missing=[r['cache'] for r in rows if not Path(r['cache']).exists()]
    if missing: raise RuntimeError(f'{len(missing)} missing extraction shards; first: {missing[:5]}')
    parts=defaultdict(list);files=[];nonfinite=Counter();sources=defaultdict(Counter)
    weight_values=set();cross_sections=set();pdgs=Counter();cutflow=None
    for row in rows:
        path=Path(row['cache'])
        with np.load(path) as d:
            report=json.loads(str(d['metadata_json']));audit=report['raw_audit']
            assert report['config']==cfg
            assert report['index']==int(row['index']) and report['input']==row['input']
            assert report['stage09_cutflow_verified'] and report['stage10_selected_keys_verified']
            assert report['selected_events']==int(row['expected_selected'])
            assert audit['events']==int(row['expected_events'])
            assert audit['invalid_first_energy']==0 and audit['truth_alignment_failures']==0
            assert not any(audit['used_track_alignment_failures'].values())
            data={k:d[k] for k in d.files if k not in ['metadata_json','cutflow_names','cutflow_passed']}
            data['group']=np.full(report['selected_events'],row['group'])
            parts[row['partition']].append(data)
            if cutflow is None: cutflow=np.zeros_like(d['cutflow_passed']);cut_names=d['cutflow_names']
            cutflow+=d['cutflow_passed']
        nonfinite.update(report['feature_nonfinite_counts']);pdgs.update(audit['truth_first_pdg_counts'])
        weight_values.update(audit['genweight_values']);cross_sections.update(audit['cross_sections'])
        sources[row['run']].update(files=1,raw_events=audit['events'],selected_events=report['selected_events'])
        files.append(dict(index=row['index'],run=row['run'],partition=row['partition'],input=row['input'],
                          events=audit['events'],selected=report['selected_events'],
                          audit_wall_s=audit['audit_wall_s'],analysis_wall_s=report['analysis_wall_s'],
                          total_wall_s=report['total_wall_s'],analysis_peak_rss_MiB=report['analysis_peak_rss_MiB'],
                          parent_peak_rss_MiB=report['parent_peak_rss_MiB'],cache_bytes=path.stat().st_size,
                          nonfinite_features=sum(report['feature_nonfinite_counts'].values()),
                          max_spacepoints=audit['spacepoints_max'],
                          max_relative_truth_P_difference=audit['truth_P_component_max_relative_difference'],
                          max_relative_label_difference=report['max_label_relative_component_difference'],
                          max_E_minus_pz_GeV=audit['truth_E_minus_pz_max_GeV']))
    destination=Path(rows[0]['cache']).parents[1]/'dataset';destination.mkdir(parents=True,exist_ok=True)
    partitions=[];all_keys=[];all_fingerprints={};cross_partition_duplicates=0
    for part,shards in parts.items():
        data={k:np.concatenate([d[k] for d in shards]) for k in shards[0]}
        keys=np.column_stack([data['run'],data['eventID']]);all_keys.append(keys)
        n=len(keys)
        truth_cols=['ML_truth_px_MeV','ML_truth_py_MeV','ML_truth_pz_MeV','truth_dec_x_nu','truth_dec_y_nu','truth_dec_z_nu']
        # Challenge flux samples are independent domains, still audit exact duplicates.
        for fingerprint in map(tuple,np.column_stack([data[c] for c in truth_cols])):
            if fingerprint in all_fingerprints and all_fingerprints[fingerprint]!=part:
                cross_partition_duplicates+=1
            all_fingerprints[fingerprint]=part
        out=destination/f'{part}.npz'
        np.savez_compressed(out,**data,config_json=np.array(json.dumps(cfg)))
        # Reopen and verify every stored event/feature before allowing shard removal.
        with np.load(out) as checked:
            for k,value in data.items():
                if value.dtype.kind in 'fc':np.testing.assert_allclose(checked[k],value,rtol=0,atol=0,equal_nan=True)
                else:np.testing.assert_array_equal(checked[k],value)
        partitions.append(dict(partition=part,files=len(shards),groups=len(np.unique(data['group'])),events=n,
                               sum_w=float(n),sum_w2=float(n),Neff=float(n),cache_bytes=out.stat().st_size,path=str(out)))
    all_keys=np.concatenate(all_keys)
    assert len(np.unique(all_keys,axis=0))==len(all_keys)==104930
    assert not cross_partition_duplicates,'Exact repeated incoming kinematics + vertex cross partitions'
    source_rows=[dict(run=run,**counts,sum_w=float(counts['selected_events']),sum_w2=float(counts['selected_events']),Neff=float(counts['selected_events'])) for run,counts in sorted(sources.items())]
    write_table(args.output_dir/'extraction_files.tsv',files)
    write_table(args.output_dir/'extraction_sources.tsv',source_rows)
    write_table(args.output_dir/'partitions.tsv',partitions)
    write_table(args.output_dir/'extraction_cutflow.tsv',[dict(cut=name,passed=int(n)) for name,n in zip(cut_names,cutflow)])
    report=dict(files=len(rows),raw_events=sum(r['events'] for r in files),selected_events=len(all_keys),
                feature_nonfinite_counts=dict(nonfinite),genweight_values=sorted(weight_values),cross_sections=sorted(cross_sections),
                raw_first_pdg_counts=dict(pdgs),cross_partition_exact_truth_duplicates=cross_partition_duplicates,
                max_spacepoints=max(r['max_spacepoints'] for r in files),
                max_relative_truth_P_difference=max(r['max_relative_truth_P_difference'] for r in files),
                max_relative_label_difference=max(r['max_relative_label_difference'] for r in files),
                max_E_minus_pz_GeV=max(r['max_E_minus_pz_GeV'] for r in files),
                sum_extraction_wall_s=sum(r['total_wall_s'] for r in files),
                extraction_wall_quantiles_s=np.quantile([r['total_wall_s'] for r in files],[0,.5,.9,1]).tolist(),
                max_analysis_rss_MiB=max(r['analysis_peak_rss_MiB'] for r in files),
                max_parent_rss_MiB=max(r['parent_peak_rss_MiB'] for r in files),
                original_cache_bytes=sum(r['cache_bytes'] for r in files),
                consolidated_cache_bytes=sum(r['cache_bytes'] for r in partitions),
                weight_mode='unit diagnostic; physical flux normalization unverified',config=cfg)
    (args.output_dir/'extraction_summary.json').write_text(json.dumps(report,indent=2)+'\n')
    if args.remove_shards:
        for row in rows:Path(row['cache']).unlink()
    print(json.dumps({k:v for k,v in report.items() if k!='config'}),flush=True)


if __name__=='__main__':
    main()
