"""Fixed local segment angles and within-station position-slope controls (stage51)."""
import json
from pathlib import Path
import numpy as np

REPO=Path(__file__).resolve().parents[1]
OUT=REPO/'workbook/stage51_energy_ml'
CACHE=REPO/'ntuples/energy_ml_stage51'
FIELDS=['x','y','z','px','py','pz','Chi2','nDoF']
CENTERS=np.array([-1860.15,47.4,1237.4,2427.4])


def configuration():
    return json.loads((REPO/'ml/configs/segment_information.json').read_text())


def feature_names():
    angle=[f's{s}_{key}' for s in range(4) for key in ['theta_q25_mrad','theta_q50_mrad','theta_q75_mrad','theta_q90_mrad','mean_tx_mrad','mean_ty_mrad','std_tx_mrad','std_ty_mrad','mean_cos_phi','mean_sin_phi']]
    angle += [f's{s}_mu_relative_{key}_mrad' for s in [0,1,3] for key in ['q50','q90']]
    convergence=[f's{s}_local_{key}' for s in range(4) for key in ['minimum_dz_mm','minimum_rms_mm','center_rms_mm','upstream_rms_mm','downstream_rms_mm','relative_10pct_width_mm']]
    return angle,convergence


def matrix(row,prefix):
    return np.array([row[prefix+k] for k in FIELDS],float).T.reshape(-1,8)


def valid_segments(a,cfg):
    distance=abs(a[:,2,None]-CENTERS)
    st=distance.argmin(axis=1)
    valid=np.isfinite(a).all(axis=1)&(a[:,5]>0)&(a[:,7]>=0)&(distance.min(axis=1)<=cfg['station_z_tolerance_mm'])
    valid &= ~(abs(a)==999999).any(axis=1)
    return st,valid


def convergence(pos,slope,cfg):
    if len(pos)<2:return np.full(6,np.nan)
    # All positions are translated by <=1 mm to their fitted station centre.
    a=pos-pos.mean(axis=0);b=slope-slope.mean(axis=0)
    aa=float(np.mean(np.sum(b*b,axis=1)));bb=float(np.mean(np.sum(a*b,axis=1)));cc=float(np.mean(np.sum(a*a,axis=1)))
    h=cfg['convergence_half_span_mm'];minimum=float(np.clip(-bb/aa,-h,h)) if aa>0 else 0.
    def curve(z):return np.maximum(0.,aa*z*z+2*bb*z+cc)
    grid=np.linspace(-h,h,cfg['convergence_grid_points']);values=curve(grid);best=float(curve(minimum))
    # Geometric width relative to the minimum dispersion; not a likelihood or vertex error.
    width=float(np.sum(values<=1.1*best+1e-12)*(2*h/(len(grid)-1)))
    width=min(2*h,width)
    return np.array([minimum,np.sqrt(best),np.sqrt(cc),np.sqrt(curve(-h)),np.sqrt(curve(h)),width])


def summarize(a,axis,run,event,index,cfg):
    st,valid=valid_segments(a,cfg);a=a[valid];st=st[valid]
    angles=[];relative=[];actual=[];null=[];counts=[];changed=0;duplicates=0
    # Stable identity-specific seeds: no dependence on labels, fold or event processing order.
    rng=np.random.default_rng(np.random.SeedSequence([cfg['shuffle_seed'],int(run),int(event),int(index)]))
    for s in range(4):
        v=a[st==s]
        # Only exact duplicate stored segments are removed, identically for all candidates.
        before=len(v);v=np.unique(v,axis=0);duplicates+=before-len(v);counts.append(len(v))
        if not len(v):angles += [np.nan]*10;relative.append([np.nan]*2);actual.extend([np.nan]*6);null.extend([np.nan]*6);continue
        slope=v[:,3:5]/v[:,5,None];theta=np.arctan(np.linalg.norm(slope,axis=1));az=np.arctan2(slope[:,1],slope[:,0])
        angles.extend(list(np.quantile(theta,[.25,.5,.75,.9])*1000)+list(slope.mean(axis=0)*1000)+list(slope.std(axis=0)*1000)+[np.cos(az).mean(),np.sin(az).mean()])
        j={0:0,1:1,3:2}.get(s)
        if j is not None and np.isfinite(axis[j]).all():
            u=np.column_stack([slope,np.ones(len(slope))]);m=np.r_[axis[j,2:],1.]
            # Actual angle between local tangents, stable also for large slopes.
            angle=np.arctan2(np.linalg.norm(np.cross(u,m),axis=1),u@m)
            relative.append(list(np.quantile(angle,[.5,.9])*1000))
        else:relative.append([np.nan]*2)
        pos=v[:,:2]+slope*(CENTERS[s]-v[:,2,None])
        actual.extend(convergence(pos,slope,cfg))
        # The input position set is the set translated to the same reference plane.
        # A random permutation preserves each marginal; fixed points are reported.
        permutation=rng.permutation(len(v));changed+=int((permutation!=np.arange(len(v))).sum())
        null.extend(convergence(pos,slope[permutation],cfg))
    angles += list(np.array(relative)[[0,1,3]].ravel())
    real=np.array(actual,'float32');shuffled=np.array(null,'float32');theta=np.array(angles,'float32')
    np.testing.assert_array_equal(np.isnan(real),np.isnan(shuffled))
    # Center dispersion and all angular features are exactly unchanged by the control.
    np.testing.assert_array_equal(real[2::6],shuffled[2::6])
    return theta,real,shuffled,np.array(counts),dict(shuffled_pairings_N=changed,exact_duplicate_N=duplicates)


def formal_output(f,d):
    """Live fold shard or archived metadata plus single merged prediction copy."""
    path=REPO/f'ml/artifacts/stage51/formal/{f}'
    if (path/'predictions.npz').exists():
        with np.load(path/'predictions.npz') as z:return {k:z[k] for k in z.files}
    md=json.loads((path/'metadata.json').read_text());r=md['records'][0]
    roles={key:np.flatnonzero(np.isin(d['group'],r[role+'_sources'])) for key,role in [('cache_row','evaluation'),('train_cache_row','train'),('cal_cache_row','calibration')]}
    with np.load(CACHE/'predictions.npz') as z:values={r['model']:z[r['model']][roles['cache_row']] for r in md['records']}
    return dict(roles,**values,metadata_json=np.array(json.dumps(md)))
