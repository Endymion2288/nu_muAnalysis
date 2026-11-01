#!/usr/bin/env python3
"""Freeze a physics-stratified native audit, without selecting response tails."""
import csv,json,time,argparse
from pathlib import Path
import numpy as np
import yaml,uproot
from train_bdt import write_table

def main():
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args();repo=a.repo;tick=time.perf_counter()
 cfg=yaml.safe_load((repo/'ml/configs/reference_audit.yaml').read_text());rng=np.random.default_rng(cfg['seed'])
 rows=list(csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t'));chosen=[];sets={}
 for part in cfg['partitions']:
  with np.load(repo/f'ntuples/energy_ml_stage12/dataset/{part}.npz') as z:base={k:z[k] for k in z.files if k!='config_json'}
  with np.load(repo/f'ntuples/energy_ml_stage15/{part}_truth.npz') as z:truth={k:z[k] for k in z.files if k!='config_json'}
  np.testing.assert_array_equal(base['eventID'],truth['eventID']);sets[part]=(base,truth)
 for comp in cfg['components']:
  for part in cfg['partitions']:
   group=sorted({r['group'] for r in rows if r['component']==comp and r['partition']==part})[0]
   chosen += [r for r in rows if r['group']==group and r['partition']==part]
 out=repo/'ntuples/energy_ml_stage32/requests';out.mkdir(parents=True,exist_ok=True);manifest=[];sample=[]
 for row in chosen:
  base,t=sets[row['partition']];indices=np.flatnonzero(base['manifest_index']==int(row['index']));strata={}
  for idx in rng.permutation(indices):
   key=tuple(np.searchsorted(cfg[edge],t[field][idx],side='right')-1 for edge,field in [('energy_edges_GeV','truth_E_GeV'),('y_edges','y_lepton'),('vertex_z_edges_mm','vertex_z_mm')])
   strata.setdefault(key,[]).append(int(idx))
  selected=[]
  while len(selected)<cfg['truth_events_per_file']:
   for energy in sorted({key[0] for key in strata}):
    keys=[key for key in strata if key[0]==energy and strata[key]]
    if keys and len(selected)<cfg['truth_events_per_file']:
     key=keys[int(rng.integers(len(keys)))];selected.append(strata[key].pop())
  with uproot.open(row['input']) as f:ids=f['nt']['eventID'].array(library='np')
  lookup={int(e):i for i,e in enumerate(ids)};cov=[]
  for mask in [lambda v:v<400,lambda v:v>=1600]:
   candidates=[i for i in selected if mask(t['primary_p_GeV'][i]) and i not in cov]
   if not candidates:candidates=[i for i in selected if i not in cov]
   cov.append(int(rng.choice(candidates)))
  events=[]
  for idx in selected:
   event={k:(t[k][idx].item()) for k in ['run','eventID','primary_pdg','primary_barcode','primary_p_GeV','primary_px','primary_py','primary_pz','vertex_x_mm','vertex_y_mm','vertex_z_mm','truth_E_GeV','y_lepton','lead_primary_parent_confirmed']}
   event.update(entry=lookup[int(event['eventID'])],covariance_requested=idx in cov,group=row['group'],partition=row['partition'])
   event['reco_front']=[float(base[f'ML_mu_{x}0_mm'][idx]) for x in ['x','y','z']]+[float(base['ML_mu_px0_GeV'][idx]*1000),float(base['ML_mu_py0_GeV'][idx]*1000),float(base['LeadTrack_pz0'][idx]*1000)]
   event['reco_p_GeV']=float(base['ML_mu_p_GeV'][idx]);event['reco_charge']=int(base['LeadTrack_charge'][idx]);events.append(event);sample.append(dict(index=row['index'],**{k:event[k] for k in ['run','eventID','group','partition','truth_E_GeV','primary_p_GeV','y_lepton','vertex_z_mm','lead_primary_parent_confirmed','covariance_requested']}))
  request=dict(row=row,cfg=cfg,events=events);(out/f"{row['index']}.json").write_text(json.dumps(request,separators=(',',':'))+'\n')
  manifest.append(dict(index=row['index'],run=row['run'],group=row['group'],partition=row['partition'],events=len(events),covariance_events=len(cov),input_rdo=row['input_rdo']))
 report=repo/'workbook/stage32_energy_ml';write_table(report/'manifest.tsv',manifest);write_table(report/'sample.tsv',sample)
 (report/'preparation.json').write_text(json.dumps(dict(files=len(chosen),events=len(sample),groups=len({r['group'] for r in sample}),covariance_events=sum(r['covariance_requested'] for r in sample),wall_s=time.perf_counter()-tick),indent=2)+'\n')
 print((report/'preparation.json').read_text())

if __name__=='__main__':main()
