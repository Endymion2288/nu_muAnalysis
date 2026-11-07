"""Independent record-space risk reconstruction and input/role certification."""
import csv
import json
import time

import numpy as np

from audited_features import configuration
from stage119_curve_common import masks
from stage129_energy import ROOT, OUT, CACHE, ART, load, table


def main():
    tick = time.perf_counter()
    d = load(ROOT/'ntuples/energy_ml_stage119/old_input.npz')
    names = configuration()['features']
    assert len(names)==62 and len(d['role'])==89033
    assert not any(('p0' in x or 'p1' in x or 'pz1' in x) for x in names)
    assert not np.isinf(d['x']).any() and not (d['x']==-999).any()
    assert [(d['role']==r).sum() for r in range(4)] == [17657,46575,11612,13189]
    m = load(CACHE/'measurement.npz')
    tf = load(CACHE/'timing_features.npz')
    for k, (i,j) in enumerate([(0,1),(3,4),(0,3),(1,3)]):
        good = m['present'][:,i]&m['present'][:,j]&(m['status'][:,i]==0)&(m['status'][:,j]==0)
        assert not np.isfinite(tf['features'][~good,k]).any()
        assert np.array_equal(np.isfinite(tf['features'][:,k]),tf['valid'][:,3*k+2].astype(bool))
    f = load(CACHE/'trackmaterial_features.npz')
    support=[]
    for role in [1,2,3]:
        for layer, mask in [('all',np.ones(len(d['role']),bool)),('E50_100',(d['truth_E_GeV']>=50)&(d['truth_E_GeV']<100)),('E100_200',(d['truth_E_GeV']>=100)&(d['truth_E_GeV']<200))]:
            ix=(d['role']==role)&mask;valid=ix&(f['valid'][:,1]==1)
            support.append(dict(role=role,stratum=layer,N=int(ix.sum()),two_disjoint_IFT=int(valid.sum()),conditional_p10_z_RMSE_mm=float(np.sqrt(np.mean((f['features'][valid,6]-d['vertex_z_mm'][valid])**2))) if valid.any() else None,conditional_p10_width_mean_mm=float(np.mean(f['features'][valid,7])) if valid.any() else None))
    table('trackmaterial_observable_support.tsv',support)
    records=[];comparisons=0;maximum=0.;centralmax=0.;baseline=0.
    for experiment in ['depth','material','timing','trackmaterial','saturation']:
        p=load(ART/f'{experiment}_predictions.npz')
        for a in p.values():assert not np.isfinite(a[d['role']==0]).any()
        baseline=max(baseline,float(np.nanmax(abs(p['X']-p['direct_cal']))))
        tab=list(csv.DictReader((OUT/f'{experiment}_paired.tsv').open(),delimiter='\t'))
        for role in [2,3]:
            ix=np.flatnonzero(d['role']==role)
            # Deliberately sum weighted records directly; no per-group metric
            # aggregation from the main evaluator is imported or reused.
            _,first,gid,count=np.unique(d['incoming'][ix],axis=0,return_index=True,return_inverse=True,return_counts=True)
            rng=np.random.default_rng(20261107129+role);draw=np.zeros((500,len(first)),np.int16)
            for component in sorted(set(d['component'][ix[first]])):
                groups=np.flatnonzero(d['component'][ix[first]]==component)
                draw[:,groups]=rng.multinomial(len(groups),np.full(len(groups),1/len(groups)),size=500)
            w=1/count[gid];rw=draw[:,gid]*w[None,:]
            sd={k:v[ix] for k,v in d.items() if isinstance(v,np.ndarray) and len(v)==len(d['role'])}
            layers=masks(sd);layers.update(E1600_3200=(sd['truth_E_GeV']>=1600)&(sd['truth_E_GeV']<3200),E3200_6400=(sd['truth_E_GeV']>=3200)&(sd['truth_E_GeV']<6400))
            for row in tab:
                if int(row['role'])!=role:continue
                mask=layers[row['stratum']];e1=p[row['candidate']][ix[mask]]-np.log(d['truth_E_GeV'][ix[mask]]);e0=p[row['reference']][ix[mask]]-np.log(d['truth_E_GeV'][ix[mask]])
                ww=rw[:,mask];den=ww.sum(1);a=ww@(e1**2);b=ww@(e0**2);ok=(den>0)&(b>0)
                vals={'RMSE_ratio':float(np.sqrt((w[mask]@e1**2)/(w[mask]@e0**2)))}
                vals.update(zip(['low95','high95'],np.quantile(np.sqrt(a[ok]/b[ok]),[.025,.975])))
                r1,r0=np.expm1(e1),np.expm1(e0)
                for sign,t1,t0 in [('total',abs(r1)>.5,abs(r0)>.5),('positive',r1>.5,r0>.5),('negative',r1<-.5,r0<-.5)]:
                    delta=t1.astype(float)-t0.astype(float)
                    vals[sign+'_tail_delta_pp']=100*(w[mask]@delta)/w[mask].sum()
                    vals.update(zip([sign+'_tail_low95_pp',sign+'_tail_high95_pp'],np.quantile(100*(ww[ok]@delta)/den[ok],[.025,.975])))
                diff=max(abs(float(row[k])-v) for k,v in vals.items());maximum=max(maximum,diff);comparisons+=len(vals)
                centralmax=max(centralmax,abs(float(row['RMSE_ratio'])-vals['RMSE_ratio']))
            records.append(dict(experiment=experiment,role=role,N=len(ix),incoming=len(first),record_space=True))
    assert baseline==0 and maximum<1e-10
    table('independent_validation_support.tsv',records)
    (OUT/'independent_validation.json').write_text(json.dumps(dict(paired_scalar_comparisons=comparisons,max_abs_difference=maximum,max_central_RMSE_ratio_difference=centralmax,X_baseline_max_difference=baseline,quarantine_predictions=0,reserved_predictions=0,strict_timing=True,roles_preserved=True,placeholder_minus999_N=0,infinite_input_N=0,trackmaterial_support_rebuilt_from_cached_features=True,wall_s=time.perf_counter()-tick,scope='conditional incoming bootstrap, same draws, independently record-weighted calculation; not a new blind sample'),indent=2)+'\n')


if __name__=='__main__':main()
