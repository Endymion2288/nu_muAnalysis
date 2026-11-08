"""Matched A/R/I representations; original fixed CPUhist trainer and gates."""
import json
from pathlib import Path
import numpy as np
import stage129_energy as energy
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage186_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage186';ART=ROOT/'ml/artifacts/stage186'
energy.OUT=OUT;energy.ART=ART;load=energy.load;table=energy.table

def inputs(write_cohort=False):
 d=load(ROOT/'ntuples/energy_ml_stage119/old_input.npz');n=len(d['role']);p=json.loads((OUT/'protocol.json').read_text());active=d['role']>0;seen=np.zeros(n,bool)
 q=dict(raw_pC=np.full((n,15),np.nan),ideal_pC=np.full((n,15),np.nan),common=np.zeros((n,15),bool),fit_invalid=np.full((n,15),np.nan,'float32'),censor=np.full((n,15),np.nan,'float32'),present=np.zeros((n,15),bool))
 for group in range(35):
  a=load(CACHE/f'full_{group}.npz');rows=a['row'];assert not seen[rows].any() and active[rows].all();seen[rows]=True
  np.testing.assert_array_equal(d['role'][rows],a['role']);np.testing.assert_array_equal(d['incoming'][rows].astype('float32'),a['incoming']);np.testing.assert_array_equal(d['run'][rows],a['run']);np.testing.assert_array_equal(d['eventID'][rows],a['event'])
  for k in q:q[k][rows]=a[k]
 assert seen[active].all() and not seen[~active].any()
 assert np.isfinite(q['raw_pC'][q['common']]).all() and np.isfinite(q['ideal_pC'][q['common']]).all();assert (q['ideal_pC'][q['common']]>=0).all()
 M=np.column_stack([q['common'],q['fit_invalid'],q['censor']]).astype('float32');base=energy.configuration()['features'];labels={}
 flags=[f'Q{ch}_{kind}' for kind in ['common_available','known_fit_invalid','censored'] for ch in p['channels']]
 A=np.column_stack([d['x'],M]).astype('float32');arrays={'A':A}
 labels['A']=base+flags
 for arm,k in [('R','raw_pC'),('I','ideal_pC')]:
  v=np.where(q['common'],np.arcsinh(q[k]),np.nan).astype('float32');arrays[arm]=np.column_stack([A,v]);labels[arm]=labels['A']+[f'Q{ch}_{arm}_asinh_pC' for ch in p['channels']]
 assert np.array_equal(np.isfinite(arrays['R'][:,-15:]),np.isfinite(arrays['I'][:,-15:]))
 # No new appended fields are read/filled for quarantine. X62 is a locked existing array.
 assert not np.isfinite(arrays['R'][~active,-15:]).any()
 if write_cohort:
  np.savez_compressed(CACHE/'cohort.npz',row=np.arange(n),role=d['role'],**q)
  rows=[]
  for role in [1,2,3]:
   ix=d['role']==role
   for kind in ['all']+[f'origin_{i}' for i in sorted(set(d['origin']))]+[f'component_{s}' for s in sorted(set(d['component']))]:
    use=ix.copy()
    if kind.startswith('origin_'):use &= d['origin']==int(kind[7:])
    if kind.startswith('component_'):use &= d['component']==kind[10:]
    rows.append(dict(role=role,group=kind,N=int(use.sum()),common_all15_N=int(q['common'][use].all(1).sum()),common_any_N=int(q['common'][use].any(1).sum()),missing_channel_N=int((~q['common'][use]).sum()),negative_signed_raw_N=int((q['raw_pC'][use]<0).sum()),censored_channel_N=int(np.nansum(q['censor'][use]))))
  table('energy_readout_support.tsv',rows)
 return d,arrays,labels

def write(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
