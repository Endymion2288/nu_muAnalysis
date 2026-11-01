#!/usr/bin/env python3
"""Native zero semantics and representative signal/geometry support; no causal attribution."""
import json
from pathlib import Path
import numpy as np
from report_calonu_information import strata
from train_bdt import write_table

repo=Path(__file__).resolve().parents[1]; out=repo/'workbook/stage42_energy_ml'; cache=repo/'ntuples/energy_ml_stage42'
with np.load(cache/'development.npz') as z: d={k:z[k] for k in z.files}
seen={}
for stage,filename in [(39,'cc_waveform.npz'),(40,'response.npz')]:
    with np.load(repo/f'ntuples/energy_ml_stage{stage}/{filename}') as z:
        cases=json.loads(str(z['cases_json']))
        for j,c in enumerate(cases):
            i=c['cache_row']; assert d['manifest_index'][i]==c['index'] and d['eventID'][i]==c['fingerprint']['eventID']
            record=dict(cache_row=i,index=c['index'],eventID=int(d['eventID'][i]),role=c['role'],
                        original_zero=bool(d['zero'][i]),empty_HITS=bool(z['hit_count'][j].sum()==0),
                        zero_sensitive_energy=bool((z['hit_energy_MeV'][j]==0).all()),
                        absent_all_channels=bool(~z['channel_present'][j].any()))
            if i in seen:
                for k in ['original_zero','empty_HITS','zero_sensitive_energy','absent_all_channels']: assert record[k]==seen[i][k]
            else: seen[i]=record
write_table(out/'existing_native_zero_semantics.tsv',list(seen.values()))
summary=[]
for support in ['all','regular']:
    rows=[r for r in seen.values() if support=='all' or r['role']=='regular']
    summary.append(dict(support=support,N=len(rows),zero=sum(r['original_zero'] for r in rows),
                        empty_HITS=sum(r['empty_HITS'] for r in rows),
                        zero_vs_empty_disagreement=sum(r['original_zero']!=r['empty_HITS'] for r in rows),
                        zero_vs_absent_disagreement=sum(r['original_zero']!=r['absent_all_channels'] for r in rows),
                        scope='previous native descriptive support; enriched diagnostics, not representative'))
(out/'existing_native_zero_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
if not (cache/'sensitive.npz').exists(): print(json.dumps(summary)); raise SystemExit(0)
with np.load(cache/'sensitive.npz') as z: signal=z['hit_energy_MeV']; hits=z['hit_count']; rows=z['cache_row']
local={k:v[rows] for k,v in d.items()}; masks=strata(local); energy=signal.sum(1); empty=hits.sum(1)==0; zero=local['zero']
results=[]
for label,mask in masks.items():
    if not mask.any(): continue
    n=int(mask.sum()); en=energy[mask]; positive=en[en>0]; transfer=(local['truth_E_GeV']*local['y_lepton'])[mask]
    valid=np.isfinite(transfer)&(transfer>=0)
    corr=float(np.corrcoef(np.log1p(en[valid]),np.log1p(transfer[valid]))[0,1]) if valid.sum()>2 and en[valid].std()>0 else None
    results.append(dict(stratum=label,N=n,sources=len(np.unique(local['group'][mask])),
                        empty_HITS=int(empty[mask].sum()),zero_S=int((en==0).sum()),original_zero=int(zero[mask].sum()),
                        original_zero_but_nonempty_HITS=int((mask&zero&~empty).sum()),
                        nonzero_original_but_empty_HITS=int((mask&~zero&empty).sum()),
                        signal_MeV_median=float(np.median(en)),signal_MeV_p90=float(np.quantile(en,.9)),
                        signal_MeV_p99=float(np.quantile(en,.99)),signal_MeV_max=float(en.max()),
                        positive_signal_MeV_median=float(np.median(positive)) if len(positive) else None,
                        transfer_GeV_median=float(np.nanmedian(transfer)),
                        corr_log1p_sensitive_MeV_log1p_transfer_GeV=corr))
write_table(out/'signal_support.tsv',results)
print(json.dumps(dict(B_events=len(rows),empty=int(empty.sum()),original_zero=int(zero.sum()))))
