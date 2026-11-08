"""Independent rational energy identities, primary association and charge joins."""
import csv,gzip,json,math
from fractions import Fraction as F
from pathlib import Path
import numpy as np
ROOT=Path.cwd();OUT=ROOT/'workbook/stage187_energy_ml';P=json.loads((OUT/'protocol.json').read_text());saved=json.loads((OUT/'ledger.json').read_text())
def gz(path):
 with gzip.open(path,'rt') as f:return json.load(f)
def rounded(value,exact):
 assert math.isfinite(value)
 assert F(float(np.nextafter(value,-np.inf)))<=exact<=F(float(np.nextafter(value,np.inf))),(value,float(exact))
checks=[];max_gap=0.;continuity_nonzero=0;rational_segments=0
assert [r['index'] for r in saved['parents']]==P['parents']
for r in saved['parents']:
 i=r['index'];raw=gz(ROOT/f'ntuples/energy_ml_stage{176 if i==50 else 178}/parent_{i}_lineage.json.gz');primary=raw['muon_primaries'];assert len(primary)==1
 root=int(primary[0][0]);steps=[s for s in raw['muon_segments'] if int(s[0])==root];initial=F(primary[0][8]);first=F(steps[0][7]);last=F(steps[-1][8]);drop=sum((F(s[7])-F(s[8]) for s in steps),F(0));gaps=sum((F(b[7])-F(a[8]) for a,b in zip(steps,steps[1:])),F(0))
 assert initial-last==drop-gaps-(first-initial)
 assert r['primary_segments_N']==len(steps) and r['primary_root']==root
 for key,value in [('initial_E_GeV',initial/1000),('final_E_GeV',last/1000),('initial_minus_final_GeV',(initial-last)/1000),('sum_step_drops_GeV',drop/1000),('sum_adjacent_gaps_GeV',gaps/1000),('first_minus_initial_MeV',first-initial)]:rounded(r[key],value)
 observed=[abs(F(b[7])-F(a[8])) for a,b in zip(steps,steps[1:])];gap=max(observed,default=F(0));rounded(r['max_abs_adjacent_gap_MeV'],gap);max_gap=max(max_gap,float(gap));continuity_nonzero+=sum(v!=0 for v in observed);rational_segments+=len(steps)
 side=json.loads((ROOT/f'workbook/stage178_energy_ml/parent_{i}_intervals.json').read_text());forward=[c for c in side['robust_crossings'] if c['forward']];assert r['plane_supported']==side['state_supported'] and r['forward_crossings_N']==len(forward)
 if forward:
  c=forward[0];assert r['cross_ordinal']==c['ordinal'];s=raw['muon_segments'][c['ordinal']];assert s[7:9]==c['pre_post_total_energy_MeV']
  box=side['plane_box'];signs=[]
  for xyz in [s[1:4],s[4:7]]:
   lo=F(0);hi=F(0)
   for x,center,momentum in zip(xyz,box['xyz_mm_intervals'],box['momentum_MeV_intervals']):
    products=[(F(x)-F(y))*F(m) for y in center for m in momentum];lo+=min(products);hi+=max(products)
   signs.append(-1 if hi<0 else 1 if lo>0 else 0)
  assert signs==[-1,1]
  for key,value in [('cross_pre_E_GeV',F(s[7])/1000),('cross_post_E_GeV',F(s[8])/1000),('loss_to_cross_pre_GeV',(initial-F(s[7]))/1000),('loss_to_cross_post_GeV',(initial-F(s[8]))/1000)]:rounded(r[key],value)
 else:assert all(r[k] is None for k in ['cross_ordinal','cross_pre_E_GeV','cross_post_E_GeV','loss_to_cross_pre_GeV','loss_to_cross_post_GeV'])
 with np.load(ROOT/'ntuples/energy_ml_stage131/matched_input.npz') as z:
  ix=np.flatnonzero(z['frame_index']==i);association=len(ix)==1 and bool(z['confirmed'][ix[0]] and z['primary_valid'][ix[0]]);assert r['confirmed_primary_association']==association
  if association and side['plane_box']['supported']:
   from decimal import Decimal,localcontext
   with localcontext() as ctx:
    ctx.prec=70;v=side['plane_box']['cached_values'][3:];exact=sum((F(x)*1000)**2 for x in v)+F(P['muon_mass_MeV'])**2;target=(Decimal(exact.numerator)/Decimal(exact.denominator)).sqrt()/1000
    lo=hi=r['cached_fit_E_GeV']
    for _ in range(4):lo=float(np.nextafter(lo,-np.inf));hi=float(np.nextafter(hi,np.inf))
    assert Decimal.from_float(lo)<=target<=Decimal.from_float(hi)
   if forward:
    for side_name in ['pre','post']:rounded(r[f'fit_minus_cross_{side_name}_GeV'],F(r['cached_fit_E_GeV'])-F(r[f'cross_{side_name}_E_GeV']))
  else:assert r['cached_fit_E_GeV'] is None
 checks.append(dict(index=i,passed=True,segments_N=len(steps),plane=r['plane_supported'],confirmed_primary=association,max_abs_energy_gap_MeV=float(gap)))
original=list(csv.DictReader((ROOT/'workbook/stage179_energy_ml/charge_interventions.tsv').open(),delimiter='\t'));charge_checks=0
for q in saved['sources']:
 rows=[r for r in original if int(r['index'])==q['index'] and r['detector']==q['detector']];assert len(rows)==q['channels_N']
 for k in ['primary_muon_direct_pC','before_S0_pC','after_S0_pC','other_root_pC','unknown_root_pC','unknown_S0_pC','total_ideal_pC']:
  key='ideal_no_noise_no_clip_no_quantization_pC' if k=='total_ideal_pC' else k;rounded(q[k],sum((F(float(r[key])) for r in rows),F(0)));charge_checks+=1
result=dict(passed=True,parents_N=len(checks),plane_N=sum(r['plane'] for r in checks),unknown_planes=[r['index'] for r in checks if not r['plane']],confirmed_primary_N=sum(r['confirmed_primary'] for r in checks),rational_primary_segments_N=rational_segments,energy_telescoping_exact=True,nonzero_adjacent_energy_gaps_N=continuity_nonzero,max_abs_adjacent_gap_MeV=max_gap,charge_scalar_joins_N=charge_checks,cached_fit_sqrt_forward_rounding_bound_ULPs=4,checks=checks,new_fits=0,new_forward=0,new_G4=0,promotion=False,overall_complete=False)
(OUT/'independent_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)
