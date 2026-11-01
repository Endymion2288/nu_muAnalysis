#!/usr/bin/env python3
"""Predefined support description; historical comparison is not a causal subtraction."""
import json
import numpy as np
from source_transfer import REPO,CACHE,OUT

with np.load(CACHE/'selection.npz') as z:rows=z['cache_row']
with np.load(REPO/'ntuples/energy_ml_stage42/development.npz') as z:cache={k:z[k] for k in z.files}
records=[]
for name,ids in [('historical_21_sources',np.flatnonzero(cache['selected'])),('external_60_sources',rows)]:
 d={k:v[ids] for k,v in cache.items()};p=d['reco_p_GeV'];focus=(p>=100)&(p<1000);y=d['y_lepton'];en=d['truth_E_GeV'];z=d['vertex_z_mm']
 records.append(dict(support=name,N=len(ids),focus_N=int(focus.sum()),source_N=len(set(d['group'])),
                     component_N={c:int((d['component']==c).sum()) for c in ['pi','k','charm']},
                     focus_component_N={c:int(((d['component']==c)&focus).sum()) for c in ['pi','k','charm']},
                     focus_high_y_N=int((focus&(y>=.8)).sum()),focus_unknown_y_N=int((focus&~np.isfinite(y)).sum()),
                     focus_proxy_failed_N=int((focus&~d['primary_kinematic_parent_proxy']).sum()),
                     focus_energy_bin_N=np.histogram(en[focus],bins=[100,200,400,800,1600,3200,6400])[0].tolist(),
                     focus_z_region_N=[int((focus&(z>=a)&(z<b)).sum()) for a,b in [(-3000,-2928),(-2812,-2600),(-2600,-2300),(-2300,-1950),(-1769.65,-1619.65)]],
                     focus_reco_p_quantiles_GeV=np.quantile(p[focus],[.1,.5,.9]).tolist(),
                     focus_E_quantiles_GeV=np.quantile(en[focus],[.1,.5,.9]).tolist(),focus_y_quantiles=np.quantile(y[focus],[.1,.5,.9]).tolist()))
(OUT/'support_description.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records))
