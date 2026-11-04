"""Stage97 identity, units/domain and saved pairing audit; no PHYS or fit."""
import json
import time
import numpy as np
from prepare_candidate_ablation import REPO,CACHE,arrays,cost
from joint_candidate_common import save


def main():
    start=time.perf_counter(),time.process_time()
    c=arrays(CACHE/'candidates.npz');s=arrays(REPO/'ntuples/energy_ml_stage87/split.npz')
    rows=np.flatnonzero(s['role']>0);np.testing.assert_array_equal(rows,c['row'])
    n=np.diff(c['offsets']);ec=np.diff(c['edge_offsets']);available=c['available']
    assert np.array_equal(ec,np.maximum(n-1,0)) and (n[available]>0).all() and (n[~available]==0).all()
    assert len(c['nodes'])==75220 and len(c['edges'])==4888
    left=np.repeat(c['offsets'][:-1],ec)
    right=np.concatenate([np.arange(c['offsets'][i]+1,c['offsets'][i+1]) for i in np.flatnonzero(ec)])
    a=c['nodes'][left].astype(float);b=c['nodes'][right].astype(float)
    values=[np.hypot(a[:,i]-b[:,i],a[:,j]-b[:,j]) for i,j in [(7,8),(20,21),(16,17)]]
    values.append(np.hypot(a[:,1]/a[:,0]-b[:,1]/b[:,0],a[:,2]/a[:,0]-b[:,2]/b[:,0]))
    values.append(np.where(np.isfinite(a[:,3])&np.isfinite(b[:,3]),a[:,3]==b[:,3],np.nan))
    expected=np.column_stack(values)
    np.testing.assert_allclose(expected,c['edges'],rtol=2e-6,atol=2e-4,equal_nan=True)
    assert not np.isinf(c['nodes']).any() and not np.isinf(c['edges']).any()
    for j in [0,4,5,6]:
        v=c['nodes'][:,j];valid=np.isfinite(v)
        assert (v[valid]>0).all() if j==0 else (v[valid]>=0).all()
    for j in list(range(7,13))+list(range(16,22)):
        assert not np.isin(c['nodes'][:,j],[-999,-999999,999999]).any()
    cfg=json.loads((REPO/'ml/configs/audited_features.json').read_text())
    assert not any(k in cfg['features'] for k in cfg['removed_features'])
    assert all(name+'_raw_charge' in cfg['features'] for name in cfg['scintillators'])
    assert not any(name+'_charge' in cfg['features'] for name in cfg['scintillators'])
    support=[]
    for role in [1,2,3]:
        use=s['role'][rows]==role
        _,inv=np.unique(s['key_id'][rows][use],return_inverse=True)
        np.testing.assert_allclose(np.bincount(inv,weights=s['weight'][rows][use]),1,rtol=0,atol=1e-12)
        support.append(dict(role=role,N=int(use.sum()),incoming=int(len(np.unique(inv))),
             available=int((use&available).sum()),unavailable=int((use&~available).sum()),
             single=int((use&(n==1)).sum()),multiple=int((use&(n>1)).sum()),
             additional_K=int((use&(s['origin'][rows]==82)).sum())))
    sets=[set(s['key_id'][s['role']==r]) for r in [1,2,3]]
    assert not any(sets[i]&sets[j] for i in range(3) for j in range(i+1,3))
    assert sum(v['additional_K'] for v in support)==1016
    save('input_audit.json',dict(passed=True,support=support,quarantine=int((s['role']==0).sum()),
         edge_correspondence_comparisons=int(expected.size),edge_max_absolute_difference=np.nanmax(abs(expected-c['edges']),axis=0).tolist(),
         first_power_momentum='pz0-only',scintillator_fitted_charge_features=0,raw11_status_preserved=True,
         preserved_charge_minus_one=int((c['nodes'][:,3]==-1).sum()),preserved_module_eta_minus_one=int((c['nodes'][:,13]==-1).sum()),
         new_PHYS_reads=0,new_fits=0,new_predictions=0,**cost(start)))
    print((REPO/'workbook/stage97_energy_ml/input_audit.json').read_text())


if __name__=='__main__':main()
