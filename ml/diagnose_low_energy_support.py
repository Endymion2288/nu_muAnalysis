#!/usr/bin/env python3
"""Full nominal development QA of low-energy muon response and selected mixture.

Truth matching is diagnostic only; no events are removed from model evaluation.
"""
import csv,json,resource,time
from pathlib import Path
import numpy as np
from train_bdt import write_table
from report_low_energy import metrics

repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage55_energy_ml';tick,cpu=time.perf_counter(),time.process_time()
rows=[r for r in csv.DictReader((repo/'ml/configs/low_energy_files.tsv').open(),delimiter='\t') if r['family']=='nominal' and r['partition']=='validation']
columns=['run','eventID','truth_E_GeV','reco_p_GeV','primary_p_GeV','primary_valid','confirmed','y_lepton','source']
consolidated=repo/'ntuples/energy_ml_stage55/dataset.npz'
if consolidated.exists():
 with np.load(consolidated) as z:
  m=z['nominal']&(z['partition']=='validation');d={k:z[k][m] for k in columns+['group']}
else:
 parts=[]
 for r in rows:
  with np.load(repo/f"ntuples/energy_ml_stage55/shards/{r['index']}.npz") as z:
   d={k:z[k] for k in columns}
   d['group']=np.full(len(d['run']),r['group']);parts.append(d)
 d={k:np.concatenate([p[k] for p in parts]) for k in parts[0]}
masks={f'true_E{lo}_{hi}':(d['truth_E_GeV']>=lo)&(d['truth_E_GeV']<hi) for lo,hi in [(50,75),(75,100),(50,100),(100,200)]}
masks.update({f'confirmed_true_p{lo}_{hi}':d['confirmed']&(d['primary_p_GeV']>=lo)&(d['primary_p_GeV']<hi) for lo,hi in [(50,100),(100,250),(250,1000)]})
records=[];response=[]
for name,m in masks.items():
 y=d['y_lepton'][m];p=d['primary_p_GeV'][m];valid=d['primary_valid'][m]
 records.append(dict(stratum=name,N=int(m.sum()),groups=len(set(d['group'][m])),sources=len(set(d['source'][m])),confirmed_N=int(d['confirmed'][m].sum()),primary_valid_N=int(valid.sum()),mean_y=float(np.nanmean(y)),median_y=float(np.nanmedian(y)),y_ge0p8_N=int((y>=.8).sum()),median_primary_p_GeV=float(np.nanmedian(p)),median_reco_p_GeV=float(np.median(d['reco_p_GeV'][m]))))
 m=m&d['confirmed']&np.isfinite(d['primary_p_GeV'])&(d['primary_p_GeV']>0)
 if m.any():response.append(dict(stratum=name,N=int(m.sum()),groups=len(set(d['group'][m])),**metrics(np.log(d['primary_p_GeV'][m]),np.log(d['reco_p_GeV'][m]))))
write_table(out/'nominal_low_energy_composition.tsv',records);write_table(out/'nominal_muon_response.tsv',response)
md=dict(wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,scope='reconstructed p vs primary production p, not a same-plane pull; source-disjoint development only; confirmed subset diagnostic')
(out/'support_diagnosis_resources.json').write_text(json.dumps(md,indent=2)+'\n');print(json.dumps(dict(composition=records,response=response,resources=md),indent=2))
