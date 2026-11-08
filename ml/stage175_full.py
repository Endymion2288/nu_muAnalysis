from concurrent.futures import ProcessPoolExecutor
import csv
from stage175_common import *
from stage175_tails import diagnostics
if __name__=='__main__':
    tick=time.perf_counter()
    with ProcessPoolExecutor(max_workers=8) as pool:rows=list(pool.map(read,[(i,'full') for i in range(len(sources()))]))
    parts=[]
    for i in range(len(sources())):
        with np.load(CACHE/f'full_{i}.npz') as z:d={k:z[k] for k in z.files}
        if i in plan()['pilot_indices']:
            with np.load(CACHE/f'pilot_{i}.npz') as old:
                pos=np.searchsorted(d['row'],old['row']);np.testing.assert_array_equal(d['row'][pos],old['row'])
                for key in old.files:np.testing.assert_array_equal(d[key][pos],old[key])
        parts.append(d)
    d={k:np.concatenate([r[k] for r in parts]) for k in parts[0]};order=np.argsort(d['row']);d={k:v[order] for k,v in d.items()}
    np.testing.assert_array_equal(d['row'],np.arange(89033));flags,value=means(d)
    with np.load(ROOT/'ntuples/energy_ml_stage119/old_input.npz') as old:
        np.testing.assert_array_equal(d['role'],old['role']);np.testing.assert_array_equal(d['run'],old['run']);np.testing.assert_array_equal(d['event'],old['eventID'])
        e,p,y=old['truth_E_GeV'],old['pz'],old['y_lepton'];physical=old['primary_valid'].astype(bool)&np.isfinite(y)&(y>=0)&(y<1)
        layers=dict(E50_100=(e>=50)&(e<100),E100_200=(e>=100)&(e<200),all=np.ones(len(e),bool),E200_inf=e>=200,pz50_100=(p>=50)&(p<100),pz50_100_trueE200=(p>=50)&(p<100)&(e>=200),high_y=physical&(y>=.8),unconfirmed=~old['confirmed'].astype(bool))
        support=[]
        for role in [-1,0,1,2,3]:
            for layer,m in layers.items():
                ix=m&(np.ones(len(e),bool) if role==-1 else d['role']==role)
                support.append(dict(role=role,stratum=layer,N=int(ix.sum()),physical_present=int((ix&d['present']).sum()),leading_matched=int((ix&d['track_match']).sum()),
                    pair01_strict=int(flags[ix,0].sum()),pair01_calibrated=int(flags[ix,1].sum()),pair23_strict=int(flags[ix,2].sum()),pair23_calibrated=int(flags[ix,3].sum()),any_calibrated=int((np.isfinite(value).any(1)&ix).sum()),both_calibrated=int((np.isfinite(value).all(1)&ix).sum())))
    with (OUT/'timing_support.tsv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(support[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(support)
    np.savez_compressed(CACHE/'cohort.npz',**d,flags=flags,relative_mean_ns=value)
    s0=d['s0_xyz_mm'];good=np.isfinite(s0).all(1)&(abs(s0)<1e5).all(1)&(s0!=-999).all(1)&d['track_match'];z,counts=np.unique(s0[good,2],return_counts=True)
    write('S0_inventory.json',dict(N=89033,matched_physical_finite_state_N=int(good.sum()),missing_or_placeholder_N=int((~good).sum()),
        S0_xyz_min_mm=s0[good].min(0).tolist() if good.any() else None,S0_xyz_max_mm=s0[good].max(0).tolist() if good.any() else None,
        unique_S0_z_N=len(z),S0_first64_z_values_with_counts=[[float(a),int(b)] for a,b in zip(z[:64],counts[:64])],S0_values_truncated_in_summary=len(z)>64,exact_minus999_component_N=int((s0==-999).sum()),full_values_retained_in_cohort=True,
        meaning='Actual leading Track_x0/y0/z0 from same upstream TrackParameters as pz0, source pin semantics; fitted state, not independent momentum or E_mu(vertex). Material fitter enabled in pinned source; original detailed corrections not persisted.',
        birth_and_crossing_missing=True,no_energy_correction_added=True))
    diagnostics()
    write('full_summary.json',dict(passed=True,N=89033,sources=rows,pilot_selected_rows_exact=True,all_identity_and_roles_exact=True,
        cohort_bytes=(CACHE/'cohort.npz').stat().st_size,calibrated_N=np.isfinite(value).sum(0).tolist(),
        energy_fits=0,model_forward=0,new_G4=0,wall_s=time.perf_counter()-tick,overall_complete=False,promotion=False))
    # Every original shard was joined and validated before removing it on scratch.
    for i in range(len(sources())):(CACHE/f'full_{i}.npz').unlink()
