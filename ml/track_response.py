"""Audited front/back track states; no truth in the deployment allowlist."""
import numpy as np
import awkward as ak
import yaml

TRACK_BRANCHES = ['Track_'+x for x in ['p0','px0','py0','pz0','x0','y0','z0',
                  'p1','px1','py1','pz1','x1','y1','z1','charge',
                  'module_eta0','module_phi0','z_atMaxRadius']]

def configuration(repo):
    return yaml.safe_load((repo/'ml/configs/track_response.yaml').read_text())

def derive(arrays, names, diagnostic=True):
    lengths=ak.num(arrays['Track_pz0'])
    for name in TRACK_BRANCHES + (['Track_isForward'] if diagnostic else []):
        if bool(ak.any(ak.num(arrays[name])!=lengths)):
            raise RuntimeError('Track alignment failure: '+name)
    if bool(ak.any(lengths==0)): raise RuntimeError('Empty selected track vector')
    lead=ak.argmax(arrays['Track_pz0'],axis=1,keepdims=True)
    raw={name[6:]:np.asarray(ak.to_numpy(ak.flatten(arrays[name][lead]))).astype(float) for name in TRACK_BRANCHES}
    for v in raw.values():v[(v==999999)|~np.isfinite(v)]=np.nan
    f={}
    for k in ['p1','px1','py1','pz1']:f['ML_track_'+k+'_GeV']=raw[k]/1000
    for k in ['x1','y1','z1']:f['ML_track_'+k+'_mm']=raw[k]
    with np.errstate(divide='ignore',invalid='ignore'):
        for k in ['0','1']:f['ML_track_qOverP'+k+'_GeVinv']=1000*raw['charge']/raw['p'+k]
        f['ML_track_log_p1_over_p0']=np.log(raw['p1']/raw['p0'])
        dz=raw['z1']-raw['z0'];f['ML_track_span_z_mm']=dz
        for axis in ['x','y']:
            f['ML_track_bend_'+axis]=raw['p'+axis+'1']/raw['pz1']-raw['p'+axis+'0']/raw['pz0']
            f['ML_track_chord_slope_'+axis]=(raw[axis+'1']-raw[axis+'0'])/dz
    for k in ['module_eta0','module_phi0']:f['ML_track_'+k]=raw[k]
    f['ML_track_z_atMaxRadius_mm']=raw['z_atMaxRadius']
    f['ML_event_SCT_error']=ak.to_numpy(arrays['Track_PropagationError']).astype(float)
    assert set(f)==set(names)
    for v in f.values():v[~np.isfinite(v)]=np.nan
    f.update(run=ak.to_numpy(arrays['run']),eventID=ak.to_numpy(arrays['eventID']),
             reco_p_GeV=raw['p0']/1000,reco_charge=raw['charge'])
    if diagnostic:f['lead_isForward']=ak.to_numpy(ak.flatten(arrays['Track_isForward'][lead]))
    return f

def profile(data,names):
    rows=[]
    for name in names:
        x=data[name];v=x[np.isfinite(x)].astype(float)
        q=np.quantile(v,[0,.16,.5,.84,1]) if len(v) else np.full(5,np.nan)
        rows.append(dict(feature=name,N=len(x),finite=len(v),unique=len(np.unique(v)),
                         min=q[0],q16=q[1],median=q[2],q84=q[3],max=q[4]))
    return rows
