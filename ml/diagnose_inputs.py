#!/usr/bin/env python3
"""Bounded lineage/tail QA using reconstructed and truth fields as diagnostics only."""
import argparse
import csv
import json
from functools import lru_cache
from pathlib import Path

import awkward as ak
import numpy as np
import uproot


def write(path,rows):
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args();repo=args.repo.resolve();args.output_dir.mkdir(parents=True,exist_ok=True)
    rows=list(csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t'))
    manifest={int(r['index']):r for r in rows};base=Path(rows[0]['cache']).parents[1]/'dataset'
    columns=['run','eventID','manifest_index','ML_truth_E_GeV','ML_mu_p_GeV',
             'ML_truth_px_MeV','ML_truth_py_MeV','ML_truth_pz_MeV']
    with np.load(base/'train.npz') as d:train={c:d[c] for c in columns}
    with np.load(base/'validation.npz') as d:val={c:d[c] for c in columns}
    nu_cols=['ML_truth_px_MeV','ML_truth_py_MeV','ML_truth_pz_MeV']
    train_keys=list(map(tuple,np.column_stack([train[c] for c in nu_cols])))
    val_keys=list(map(tuple,np.column_stack([val[c] for c in nu_cols])))
    lookup={k:i for i,k in enumerate(train_keys)}
    overlap=np.array([i for i,k in enumerate(val_keys) if k in lookup])
    rng=np.random.default_rng(20261029)
    sample=rng.choice(overlap,size=min(12,len(overlap)),replace=False)
    raw_columns=['truth_pdg','truth_px','truth_py','truth_pz','truth_m','truth_barcode',
                 'Track_p0','Track_pz0','t_pdg','t_barcode','t_pdg_parent','t_truthHitRatio','t_px','t_py','t_pz']
    @lru_cache(maxsize=40)
    def read(index,event):
        with uproot.open(manifest[index]['input']) as source:
            tree=source['nt'];ids=tree['eventID'].array(library='np')
            position=np.flatnonzero(ids==event).item()
            a=tree.arrays(raw_columns,entry_start=position,entry_stop=position+1)
            return {c:ak.to_list(a[c][0]) for c in raw_columns}
    lineage=[]
    for vi in sample:
        ti=lookup[val_keys[vi]]
        a=read(int(train['manifest_index'][ti]),int(train['eventID'][ti]))
        b=read(int(val['manifest_index'][vi]),int(val['eventID'][vi]))
        lineage.append(dict(train_run=int(train['run'][ti]),train_eventID=int(train['eventID'][ti]),
                            validation_run=int(val['run'][vi]),validation_eventID=int(val['eventID'][vi]),
                            energy_GeV=float(val['ML_truth_E_GeV'][vi]),
                            first_ten_pdgs_equal=a['truth_pdg']==b['truth_pdg'],
                            first_ten_momenta_equal=all(a[c]==b[c] for c in ['truth_px','truth_py','truth_pz','truth_m'])))
    write(args.output_dir/'repeated_incident_momentum_pairs.tsv',lineage)
    with np.load(repo/'ml/artifacts/stage13/validation_predictions.npz') as d:
        ratio=d['mu_p_over_0p8']/d['truth_E_GeV']
        worst=np.argsort(np.abs(ratio-1))[-10:][::-1]
    tails=[]
    for i in worst:
        raw=read(int(val['manifest_index'][i]),int(val['eventID'][i]))
        n=len(raw['Track_pz0']);lead=int(np.argmax(raw['Track_pz0']))
        aligned=all(len(raw[c])==n for c in raw_columns if c.startswith('t_'))
        row=dict(run=int(val['run'][i]),eventID=int(val['eventID'][i]),E_GeV=float(val['ML_truth_E_GeV'][i]),
                 reco_p_GeV=float(val['ML_mu_p_GeV'][i]),long_tracks=n,lead_index=lead,truth_match_vectors_aligned=aligned)
        if aligned:
            row.update(matched_pdg=raw['t_pdg'][lead],matched_barcode=raw['t_barcode'][lead],
                       matched_parent_pdg=raw['t_pdg_parent'][lead],matched_hit_ratio=raw['t_truthHitRatio'][lead],
                       matched_truth_p_GeV=float(np.sqrt(sum(raw[c][lead]**2 for c in ['t_px','t_py','t_pz']))/1000))
        tails.append(row)
    if not all(r['truth_match_vectors_aligned'] for r in tails):
        raise RuntimeError('Tail truth match indexing needs a separate alignment audit')
    write(args.output_dir/'large_proxy_tail_truth_matches.tsv',tails)
    summary=dict(train_distinct_incident_momenta=len(set(train_keys)),validation_distinct_incident_momenta=len(set(val_keys)),
                 validation_events_with_incident_momentum_in_train=len(overlap),paired_truth_audit_events=len(lineage),
                 paired_first_ten_pdgs_equal=sum(r['first_ten_pdgs_equal'] for r in lineage),
                 paired_first_ten_momenta_equal=sum(r['first_ten_momenta_equal'] for r in lineage),
                 worst_proxy_tail_events=len(tails),worst_tail_muon_truth_matches=sum(abs(r['matched_pdg'])==13 for r in tails),
                 worst_tail_min_matched_hit_ratio=min(r['matched_hit_ratio'] for r in tails),
                 note='Bounded diagnostic only; repeated incident momenta do not by themselves prove repeated GENIE interactions. No truth field enters model inputs; no events removed.')
    (args.output_dir/'lineage_and_matching_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary,flush=True)


if __name__=='__main__':
    main()
