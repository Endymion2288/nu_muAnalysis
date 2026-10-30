#!/usr/bin/env python3
"""Verify and merge stage26 disjoint permutation batches; remove duplicates."""
import json
from pathlib import Path

import numpy as np

from closure import read_table, write_table
from source_response import config


def main():
    root=Path(__file__).resolve().parents[1];cfg=config(root);removed=[];merged=[]
    for model,spec in cfg['models'].items():
        for seed in spec['seeds']:
            folder=root/f'workbook/stage26_energy_ml/{model}/seed_{seed}'
            art=root/f'ml/artifacts/stage26/{model}/seed_{seed}'
            summary_path=folder/'summary.json';base=json.loads(summary_path.read_text())
            if base['permutations_per_null']==cfg['permutations']:continue
            ext=json.loads((folder/'extension_summary.json').read_text())
            assert base['permutations_per_null']==200 and (ext['trial_start'],ext['trial_stop'])==(200,1000)
            assert base['events']==ext['events']==13375 and not base['smoke'] and not ext['smoke']
            assert ext['model']==model and ext['seed']==seed and not ext['calibration_test_challenge_evaluated']
            with np.load(art/'source_inference.npz') as z:arrays={k:z[k] for k in z.files}
            with np.load(art/'source_extension.npz') as z:extra={k:z[k] for k in z.files}
            for key in extra:
                assert arrays[key].shape[1]==200 and extra[key].shape[1]==800
                arrays[key]=np.concatenate([arrays[key],extra[key]],axis=1)
            temp=art/'source_merged.npz';np.savez_compressed(temp,**arrays)
            with np.load(temp) as check:
                for key in arrays:np.testing.assert_array_equal(check[key],arrays[key])
            temp.replace(art/'source_inference.npz')
            failures=[]
            for name in ['failures.tsv','extension_failures.tsv']:
                if (folder/name).exists():failures.extend(read_table(folder/name))
            write_table(folder/'failures.tsv',failures)
            combined={**base,'permutations_per_null':1000,'independent_event_null_partitions':1000,
                      'independent_event_coverage_partitions':200,'batches':[base,ext]}
            for key in ['failure_cells','unsupported_cases','wall_s','cpu_s']:
                combined[key]=base[key]+ext[key]
            for key in ['max_rss_KiB','maximum_kkt','maximum_start_spread']:
                combined[key]=max(base[key],ext[key])
            combined['numerical_stats']={k:base['numerical_stats'][k]+ext['numerical_stats'][k] for k in base['numerical_stats']}
            combined['host']=';'.join([base['host'],ext['host']])
            summary_path.write_text(json.dumps(combined,indent=2)+'\n')
            for p in [art/'source_extension.npz',folder/'extension_summary.json',folder/'extension_failures.tsv']:
                if p.exists():removed.append(dict(path=str(p.relative_to(root)),bytes=p.stat().st_size));p.unlink()
            merged.append(dict(model=model,seed=seed,point_trials=1000,coverage_trials=200,byte_arrays_verified=True))
    out=dict(merged=merged,removed=removed,removed_bytes=sum(r['bytes'] for r in removed))
    if merged:(root/'workbook/stage26_energy_ml/batch_merge.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))


if __name__=='__main__':main()
