#!/usr/bin/env python3
"""Full-population coverage and fold composition; no performance-driven sample choices."""
import json
import numpy as np
from learning_capacity import OUT,load_inputs,configuration

d,x=load_inputs();cfg=configuration();records=[]
for name,mask in [('A_full',np.ones(len(x),bool)),('B_21_sources',d['selected']),('remaining_60_sources',~d['selected'])]:
    p=d['reco_p_GeV'];focus=mask&(p>=100)&(p<1000)
    records.append(dict(support=name,events=int(mask.sum()),sources=len(set(d['group'][mask])),focus_events=int(focus.sum()),
                        component_N={c:int((mask&(d['component']==c)).sum()) for c in ['pi','k','charm']},
                        component_sources={c:len(set(d['group'][mask&(d['component']==c)])) for c in ['pi','k','charm']},
                        focus_component_N={c:int((focus&(d['component']==c)).sum()) for c in ['pi','k','charm']},
                        p100_250_N=int((mask&(p>=100)&(p<250)).sum()),p250_1000_N=int((mask&(p>=250)&(p<1000)).sum()),
                        p1000_up_N=int((mask&(p>=1000)).sum()),focus_high_y_N=int((focus&(d['y_lepton']>=.8)).sum()),
                        focus_unknown_y_N=int((focus&~np.isfinite(d['y_lepton'])).sum()),
                        focus_proxy_failed_N=int((focus&~d['primary_kinematic_parent_proxy']).sum()),
                        focus_E_bin_N=np.histogram(d['truth_E_GeV'][focus],cfg['energy_edges_GeV'])[0].tolist(),
                        focus_z_region_N=[int((focus&(d['vertex_z_mm']>=a)&(d['vertex_z_mm']<b)).sum()) for a,b in [(-3000,-2928),(-2812,-2600),(-2600,-2300),(-2300,-1950),(-1769.65,-1619.65)]],
                        feature_nonfinite_counts=(~np.isfinite(x[mask])).sum(axis=0).tolist()))
(OUT/'support_description.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps([{k:v for k,v in r.items() if k!='feature_nonfinite_counts'} for r in records]))
