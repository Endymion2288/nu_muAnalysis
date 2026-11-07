"""Nominal axial material-depth oracle on the full matched original support."""
import json
import shutil
import time

import numpy as np

from stage129_energy import ROOT, OUT, ART, load, table, fit, evaluate
from audited_features import configuration


def main():
    tick=time.perf_counter()
    geometry=json.loads((OUT/'geometry_intervals.json').read_text())
    volumes=geometry['intervals']
    edges=sorted(set(v[k] for v in volumes for k in ['low_mm','high_mm']))
    segments=[]
    for low,high in zip(edges,edges[1:]):
        middle=(low+high)/2
        covering=[v for v in volumes if v['low_mm']<middle<v['high_mm']]
        assert covering
        deepest=max(v['depth'] for v in covering)
        current=[v for v in covering if v['depth']==deepest]
        assert len({(v['material'],v['X0_mm'],v['lambdaI_mm']) for v in current})==1, current
        v=current[-1]
        assert v['X0_mm']>0 and v['lambdaI_mm']>0
        segments.append(dict(low_mm=low,high_mm=high,material=v['material'],X0_mm=v['X0_mm'],lambdaI_mm=v['lambdaI_mm'],depth=deepest))
    table('material_segments.tsv',segments)
    d=load(ROOT/'ntuples/energy_ml_stage119/old_input.npz')
    z=d['vertex_z_mm']
    assert np.isfinite(z).all() and z.min()>=edges[0] and z.max()<=edges[-1]
    # A precisely defined normal-incidence diagnostic coordinate, not a true
    # shower/particle path or a deployable reconstructed vertex.
    coordinates=np.zeros((len(z),2))
    for s in segments:
        length=np.maximum(s['high_mm']-np.maximum(z,s['low_mm']),0)
        coordinates[:,0]+=length/s['lambdaI_mm']
        coordinates[:,1]+=length/s['X0_mm']
    x=np.column_stack([d['x'],coordinates]).astype('float32')
    names=configuration()['features']+['oracle_remaining_lambdaI_axis_to_minus1300','oracle_remaining_X0_axis_to_minus1300']
    for arm in ['X','Z']:
        shutil.copyfile(ART/f'depth_{arm}_prediction.npz',ART/f'material_{arm}_prediction.npz')
    result=fit(('material','M',x,names,d))
    (OUT/'material_fits.json').write_text(json.dumps([result],indent=2)+'\n')
    evaluate('material',d,['X','Z','M'])
    summary=dict(N=len(z),intervals=len(volumes),segments=len(segments),ambiguous_deepest_material_segments=0,
                 lambdaI_range=coordinates[:,0].min().item(),lambdaI_max=coordinates[:,0].max().item(),
                 X0_min=coordinates[:,1].min().item(),X0_max=coordinates[:,1].max().item(),
                 truth_depth_only=True,representation='two deterministic material functions of true z, normal ray x=y=0; not independent extra information beyond truth z',
                 limitation='box-volume nominal centreline; transverse shower paths/leakage, geometry shifts and non-box material completeness are not certified here',
                 reused_X_Z_predictions='exact depth experiment predictions; no extra baseline/oracle seed selection',wall_s=time.perf_counter()-tick)
    (OUT/'material_geometry_summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':main()
