"""Conservative momentum intervals from actual G4 post-incident states."""
import numpy as np

def momentum_bound(chain,center,normal,tolerance=2e-6):
    if not chain:return dict(valid=False,reason='missing_primary')
    for left,right in zip(chain[:-1],chain[1:]):
        if left['pdg']!=right['pdg'] or right['barcode']-left['barcode']!=1000000:
            return dict(valid=False,reason='not_regenerated_parent')
        if left['end_mm'] is None or right['production_mm'] is None:
            return dict(valid=False,reason='broken_chain')
        if np.linalg.norm(np.array(left['end_mm'])-right['production_mm'])>.003:
            return dict(valid=False,reason='discontinuous_vertices')
        if right['p_GeV']>left['p_GeV']*(1+tolerance):
            return dict(valid=False,reason='nonmonotonic_momentum')
    crossings=[];normal=np.asarray(normal);center=np.asarray(center)
    for i,seg in enumerate(chain):
        if seg['production_mm'] is None or seg['end_mm'] is None:continue
        a=np.dot(np.array(seg['production_mm'])-center,normal)
        b=np.dot(np.array(seg['end_mm'])-center,normal)
        if a<=0 and b>=0:crossings.append(i)
    if len(crossings)!=1:return dict(valid=False,reason='no_unique_finite_crossing',crossings=len(crossings))
    i=crossings[0]
    if i+1>=len(chain):return dict(valid=False,reason='no_post_vertex_muon')
    low=chain[i+1]['p_GeV']*(1-tolerance);high=chain[i]['p_GeV']*(1+tolerance)
    if low<=0 or high<low:return dict(valid=False,reason='invalid_bound')
    return dict(valid=True,reason='bounded',p_low_GeV=low,p_high_GeV=high,
                upstream_vertex_z_mm=chain[i]['production_mm'][2],downstream_vertex_z_mm=chain[i]['end_mm'][2],
                interval_width_GeV=high-low)
