"""Frozen Stage115 cached-data, metrics and bootstrap helpers; batch execution."""
import csv
import io
import json
from pathlib import Path

import numpy as np

from audited_features import SCINTILLATORS, build, configuration

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage115_energy_ml'
ART = ROOT/'ml/artifacts/stage115'
LAYERS = ['E50_100','E100_200','all','E200_inf','pz50_100','pz50_100_trueE200','high_y','unconfirmed']
PROTECT = dict(all=1.01, E200_inf=1.03, pz50_100=1.03, pz50_100_trueE200=1.03, high_y=1.03, unconfirmed=1.03)
BITS = dict(overflow=4, threshold_failed=1, fit_failure=16|32, wave_invalid=8|128|256)
IO = []


def plain(v):
    if isinstance(v,dict): return {k:plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [plain(x) for x in v]
    if isinstance(v,np.ndarray): return plain(v.tolist())
    if isinstance(v,np.generic): return plain(v.item())
    if isinstance(v,float) and not np.isfinite(v): return None
    return v


def save(name,value):
    (OUT/name).write_text(json.dumps(plain(value),indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def table(name,rows):
    if not rows: return
    names=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=names,delimiter='\t',lineterminator='\n')
        w.writeheader();w.writerows({k:plain(r.get(k)) if r.get(k) is not None else 'NA' for k in names} for r in rows)


class Counted(io.BufferedReader):
    def __init__(self,path):
        super().__init__(open(path,'rb',buffering=0));self.requests=0;self.returned=0
    def read(self,n=-1):
        value=super().read(n);self.requests+=max(n,0);self.returned+=len(value);return value


def load(name,fields=None):
    path=ROOT/name
    with Counted(path) as f:
        with np.load(f,allow_pickle=False) as z:
            d={k:z[k] for k in (fields or z.files)}
        IO.append(dict(path=name,logical_bytes=path.stat().st_size,
                       local_read_requested_bytes=f.requests,local_read_returned_bytes=f.returned))
    return d


def align(source,rows):
    assert np.all(np.diff(source['row'])>0)
    i=np.searchsorted(source['row'],rows)
    assert np.all(i<len(source['row']))
    np.testing.assert_array_equal(source['row'][i],rows)
    return i


def status_features(status):
    known=np.isfinite(status)&(status>=0)&(status==np.floor(status))&(status<=511)
    integer=np.where(known,status,0).astype(np.int64)
    values=np.stack([np.where(known,(integer&b)!=0,np.nan) for b in BITS.values()],axis=2)
    return values.reshape(len(status),44).astype('float32'),known.all(1)


def cached_inputs():
    d=load('ntuples/energy_ml_stage94/evaluation_input.npz')
    split=load('ntuples/energy_ml_stage87/split.npz')
    assert len(split['role'])==89033 and (split['role']==0).sum()==17657
    np.testing.assert_array_equal(d['row'],np.flatnonzero(split['role']>0))
    for k in ['origin','origin_row','role','weight','key_id','group','block','component']:
        np.testing.assert_array_equal(d[k],split[k][d['row']])
    base=load('ml/artifacts/stage87/predictions.npz',['row','direct_cal','role','weight','truth_E_GeV','pz'])
    ib=align(base,d['row'])
    for k in ['role','weight','truth_E_GeV','pz']: np.testing.assert_array_equal(d[k],base[k][ib])
    d['base']=base['direct_cal'][ib]
    n=len(d['row']);x=np.full((n,62),np.nan,'float32');status=np.full((n,11),np.nan)
    joins=[]
    for origin in np.unique(d['origin']):
        where=np.flatnonzero(d['origin']==origin);rr=d['origin_row'][where]
        if origin==55:
            old=load('ntuples/energy_ml_stage55/dataset.npz')
            readout=load('ntuples/energy_ml_stage56/readout.npz')
            pos=np.searchsorted(readout['row'],rr)
            found=pos<len(readout['row']);found[found]&=readout['row'][pos[found]]==rr[found]
            # All current Stage87 rows were audited; missing status never deletes a row.
            small={k:v[pos[found]] for k,v in readout.items() if k!='metadata_json'}
            x[where[found]]=build(old,small);status[where[found]]=small['status']
            for k in ['incoming','group','run','eventID','component']:
                np.testing.assert_array_equal(old[k][rr],split[k][d['row'][where]])
            np.testing.assert_array_equal(d['truth_E_GeV'][where],old['truth_E_GeV'][rr])
            if not found.all():
                raise RuntimeError('Audited62 missing for original selected rows; no replacement or fitted fallback')
        else:
            z=load(f'ntuples/energy_ml_stage{origin}/support.npz')
            assert z['new_training_support'][rr].all()
            x[where]=z['x'][rr]
            if 'status' in z: status[where]=z['status'][rr]
            for k in ['incoming','group','run','eventID','component']:
                np.testing.assert_array_equal(z[k][rr],split[k][d['row'][where]])
            np.testing.assert_array_equal(d['truth_E_GeV'][where],z['truth_E_GeV'][rr])
        joins.append(dict(origin=int(origin),rows=len(where),join='origin,origin_row; incoming/run/event/group checked'))
    assert (d['pz']>50).all() and not np.isinf(x).any()
    cfg=configuration()
    np.testing.assert_array_equal(x[:,cfg['features'].index('ML_mu_pz0_GeV')],d['pz'].astype('float32'))
    assert not set(cfg['features'])&{'ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0'}
    np.testing.assert_array_equal(np.isnan(x).any(1),d['input_missing'])
    # Verify original state cleaning without reinterpreting small signed charges.
    from audited_features import clean
    np.testing.assert_array_equal(x,np.column_stack([clean(x[:,j],cfg['rules'][v]) for j,v in enumerate(cfg['features'])]).astype('float32'))
    state,available=status_features(status)
    flags=np.column_stack([d[k] for k in ['wave_invalid','fit_failure','calo_invalid']])
    a=np.column_stack([x,flags,available]).astype('float32')
    b=np.column_stack([a,state]).astype('float32')
    assert a.shape==(71376,66) and b.shape==(71376,110)
    d['status_available']=available;d['overflow_any']=np.any(state[:,0::4]==1,axis=1)
    d['threshold_any']=np.any(state[:,1::4]==1,axis=1)
    coverage=[]
    for code,count,keys in [(1,46575,37556),(2,11612,10811),(3,13189,12125)]:
        m=d['role']==code
        assert m.sum()==count and len(np.unique(d['key_id'][m]))==keys
        _,gid=np.unique(d['key_id'][m],return_inverse=True)
        np.testing.assert_allclose(np.bincount(gid,weights=d['weight'][m]),1,rtol=0,atol=1e-12)
        for j,channel in enumerate(SCINTILLATORS):
            for k,name in enumerate(BITS):
                v=state[m,4*j+k]
                coverage.append(dict(role=code,channel=channel,state=name,N=count,known_N=int(np.isfinite(v).sum()),true_N=int((v==1).sum())))
    assert int(((d['origin']==82)&(d['component']=='k')).sum())==1016
    part=load('ntuples/energy_ml_stage94/cal_partition.npz');cal=np.flatnonzero(d['role']==2);ip=align(part,d['row'][cal])
    sub=np.zeros(n,np.int8);pw=np.zeros(n);sub[cal]=part['subrole'][ip];pw[cal]=part['weight'][ip]
    assert [(sub[cal]==k).sum() for k in [0,1,2]]==[423,5443,5746]
    save('input_validation.json',dict(passed=True,active_rows=n,quarantined=17657,train=46575,cal=11612,test=13189,
         all_new_K=1016,status_available=int(available.sum()),status_missing=int((~available).sum()),
         joins=joins,baseline='saved Stage87 direct_cal including train; no new forwards',
         status_order=SCINTILLATORS,bits=BITS,feature_dimensions=dict(A=66,B=110),
         unknown_status='NaN per channel; common all-channel availability',new_split=False,new_ROOT=False))
    table('state_coverage.tsv',coverage)
    return d,dict(A=a,B=b),sub,pw


def masks(d):
    e,p=d['truth_E_GeV'],d['pz'];f=d['y_lepton'];valid=d['label_physical']
    out=dict(E50_100=(e>=50)&(e<100),E100_200=(e>=100)&(e<200),all=np.ones(len(e),bool),
        E200_inf=e>=200,pz50_100=p<100,pz50_100_trueE200=(p<100)&(e>=200),
        high_y=valid&(f>=.8),unconfirmed=~d['confirmed'],input_missing=d['input_missing'],
        status_missing=~d['status_available'],overflow_any=d['overflow_any'],threshold_any=d['threshold_any'],
        fit_failure=d['fit_failure'],response_nominal=~(d['input_missing']|d['wave_invalid']|d['fit_failure']|d['calo_invalid']),
        negative_valid_raw=d['negative_valid_raw'],confirmed_low_transfer=d['confirmed']&valid&(f<.2))
    for lo,hi in [(200,400),(400,800),(800,1600),(1600,3200),(3200,6400),(6400,np.inf)]:
        out[f'E{lo}_{"inf" if np.isinf(hi) else hi}']=(e>=lo)&(e<hi)
    return out


def metrics(y,pred,w):
    err=pred-y;rel=np.expm1(err);ii=np.argsort(rel,kind='stable');v=rel[ii];ww=w[ii]
    q=np.interp([.16,.5,.84],(np.cumsum(ww)-.5*ww)/ww.sum(),v)
    avg=lambda z:float(np.average(z,weights=w))
    return dict(log_RMSE=np.sqrt(avg(err**2)),median_bias_pct=100*q[1],mean_bias_pct=100*avg(rel),
        R68_pct=50*(q[2]-q[0]),tail50_pct=100*avg(abs(rel)>.5),positive_tail50_pct=100*avg(rel>.5),negative_tail50_pct=100*avg(rel<-.5))


def draws(d,seed):
    keys,first,gid=np.unique(d['key_id'],return_index=True,return_inverse=True)
    comp=d['component'][first];rng=np.random.default_rng(seed);draw=np.zeros((500,len(keys)),np.int16)
    for c in sorted(set(comp)):
        ix=np.flatnonzero(comp==c);draw[:,ix]=rng.multinomial(len(ix),np.full(len(ix),1/len(ix)),size=500)
    return keys,gid,draw


def ci(x):
    x=np.asarray(x);x=x[np.isfinite(x)]
    return [float(v) for v in np.quantile(x,[.025,.975])] if len(x)>=475 else [None,None]
