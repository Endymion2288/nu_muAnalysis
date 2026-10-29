#!/usr/bin/env python3
"""Freeze file-group partitions before training; retain stage09's missing index 291."""
import argparse
import csv
import random
import re
from collections import defaultdict
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    args=p.parse_args()
    repo=args.repo.resolve()
    rows=list(csv.DictReader((repo/'workbook/stage09_tracking_comparison/files.tsv').open(),delimiter='\t'))
    components={200080:'sibyll_pi',200082:'pi',200093:'pi',200083:'k',200094:'k',200089:'charm',200100:'charm'}
    groups=defaultdict(set)
    for row in rows:
        run=int(row['run'])
        generation_range=re.search(r'-(\d{5}-\d{5})-s0014-',row['input_rdo']).group(1)
        row['group']=f'{components[run]}:{generation_range}'
        groups[components[run]].add(row['group'])
    assignment={}
    rng=random.Random(20261029)
    for component, keys in sorted(groups.items()):
        keys=sorted(keys)
        rng.shuffle(keys)
        if component=='sibyll_pi':
            assignment.update({k:'challenge' for k in keys})
            continue
        n=len(keys)
        a,b,c=round(.6*n),round(.75*n),round(.85*n)
        for i,k in enumerate(keys):
            assignment[k]='train' if i<a else 'validation' if i<b else 'calibration' if i<c else 'test'
    out=[]
    for row in rows:
        out.append(dict(index=row['index'],run=row['run'],component=components[int(row['run'])],
                        group=row['group'],partition=assignment[row['group']],input_rdo=row['input_rdo'],
                        input=row['existing_merge'],expected_events=row['events'],expected_selected=row['merge_final'],
                        cache=f"/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage12/shards/{int(row['index']):03d}.npz"))
    path=repo/'ml/configs/files.tsv'
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(out[0]),delimiter='\t',lineterminator='\n')
        w.writeheader();w.writerows(out)
    assert len(out)==342 and not any(int(r['index'])==291 for r in out)
    for part in ['train','validation','calibration','test','challenge']:
        subset=[r for r in out if r['partition']==part]
        print(part,'files',len(subset),'groups',len({r['group'] for r in subset}),'expected selected',sum(int(r['expected_selected']) for r in subset))


if __name__=='__main__':
    main()
