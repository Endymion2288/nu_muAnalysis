"""Zero-fit exact cache admission for the frozen depth-by-H mechanism."""
import json
import time
import numpy as np
from stage164_common import ROOT,OUT,CACHE,load,inputs,protocol,table


def main():
    cpu,tick=time.process_time(),time.perf_counter();d=inputs();plan=protocol()
    assert plan==json.loads((ROOT/'workbook/stage163_energy_ml/next_execution_contract.json').read_text())
    assert len(d['role'])==3002 and [int((d['role']==r).sum()) for r in [1,2,3]]==[1708,653,641]
    assert np.all(d['pz']>50) and np.isfinite(d['vertex_z_mm']).all()
    assert len(np.unique(d['incoming'].astype('float32'),axis=0))==3002
    old=load('ntuples/energy_ml_stage137/fit_matrix.npz');components=load('ntuples/energy_ml_stage137/boundary_components.npz')
    np.testing.assert_array_equal(components['frame_index'],d['frame_index'])
    a=np.column_stack([d['x'],d['availability'][:,5:]]).astype('float32');h=components['log1p_KE_GeV'][:,1:2].astype('float32')
    np.testing.assert_array_equal(old['H'][:,:69],a);np.testing.assert_array_equal(old['H'][:,69:70],h)
    assert np.isnan(h).sum()==199 and np.isfinite(h).sum()==2803
    assert np.all(h[np.isfinite(h)]>=0)
    for key,value in load('ntuples/energy_ml_stage137/bootstrap_draws.npz').items():
        np.testing.assert_array_equal(value,load('ntuples/energy_ml_stage131/bootstrap_draws.npz')[key])
    frozen=load('ml/artifacts/stage137/energy_predictions.npz')
    assert all(len(frozen[n])==3002 and np.isfinite(frozen[n]).all() for n in ['A','H','X','AK','U','F','traditional','direct_cal'])
    z=d['vertex_z_mm'][:,None].astype('float32')
    az=np.column_stack([a,z]);azh=np.column_stack([a,z,h])
    np.savez_compressed(CACHE/'fit_matrix.npz',AZ=az,AZH=azh)
    support=[]
    for role in [1,2,3]:
        for component in sorted(set(d['component'])):
            use=(d['role']==role)&(d['component']==component)
            support.append(dict(role=role,component=component,N=int(use.sum()),boundary_available_N=int(np.isfinite(h[use]).sum()),
                z_min_mm=float(z[use].min()) if use.any() else None,z_max_mm=float(z[use].max()) if use.any() else None))
    table('cohort_support.tsv',support)
    result=dict(passed=True,N=3002,roles=[1708,653,641],boundary_available_N=2803,boundary_missing_N=199,
        same_A69_and_H_exact=True,same_original_500_draws=True,finite_z_same_Stage129_column=True,
        vertex_definition='truth_diagnostics: first truth particle decay_z, not fitted muon z0',
        dimensions=dict(AZ=70,AZH=71),new_fits=0,reserved_forward=0,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick)
    (OUT/'qa_summary.json').write_text(json.dumps(result,indent=2)+'\n');print(result)


if __name__=='__main__':main()
