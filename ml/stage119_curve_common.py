"""Frozen original cohort reconstruction and shared Stage119 evaluation units."""
import csv
import json
from pathlib import Path

import numpy as np

from audited_features import build, configuration

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage119'
LAYERS=['E50_100','E100_200','all','E200_inf','pz50_100','pz50_100_trueE200','high_y','unconfirmed']


def load(path):
    with np.load(ROOT/path,allow_pickle=False) as z:return {k:z[k] for k in z.files if k!='metadata_json'}


def table(name,rows):
    if not rows:return
    names=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=names,delimiter='\t');w.writeheader();w.writerows(rows)


def old_inputs():
    split=load('ntuples/energy_ml_stage87/split.npz');n=len(split['role']);x=np.full((n,62),np.nan,'float32')
    fields=['truth_E_GeV','y_lepton','primary_p_GeV','primary_valid','confirmed','vertex_z_mm']
    d={k:np.full(n,np.nan) for k in fields};d['pz']=np.full(n,np.nan)
    for origin in np.unique(split['origin']):
        ix=np.flatnonzero(split['origin']==origin);rows=split['origin_row'][ix]
        if origin==55:
            # build() needs the original feature-name metadata.
            with np.load(ROOT/'ntuples/energy_ml_stage55/dataset.npz') as z:source={k:z[k] for k in z.files}
            supplement=load('ntuples/energy_ml_stage56/readout.npz');pos=np.searchsorted(supplement['row'],rows)
            np.testing.assert_array_equal(supplement['row'][pos],rows)
            x[ix]=build(source,{k:v[pos] for k,v in supplement.items()})
        else:
            source=load(f'ntuples/energy_ml_stage{origin}/support.npz');x[ix]=source['x'][rows]
        for k in fields:d[k][ix]=source[k][rows]
        d['pz'][ix]=source['reco_pz_GeV'][rows]
        for k in ['incoming','run','eventID','component','group']:
            np.testing.assert_array_equal(source[k][rows],split[k][ix])
    d.update(split);d['x']=x
    assert n==89033 and int((d['role']==0).sum())==17657
    names=configuration()['features'];assert x.shape==(n,62)
    np.testing.assert_array_equal(x[:,names.index('ML_mu_pz0_GeV')],d['pz'].astype('float32'))
    return d


def masks(d):
    e,p,y=d['truth_E_GeV'],d['pz'],d['y_lepton'];physical=d['primary_valid'].astype(bool)&np.isfinite(y)&(y>=0)&(y<1)
    result=dict(E50_100=(e>=50)&(e<100),E100_200=(e>=100)&(e<200),all=np.ones(len(e),bool),E200_inf=e>=200,
        pz50_100=(p>=50)&(p<100),pz50_100_trueE200=(p>=50)&(p<100)&(e>=200),high_y=physical&(y>=.8),unconfirmed=~d['confirmed'].astype(bool),
        input_missing=np.isnan(d['x']).any(1),highE=e>=1000,upstream=d['vertex_z_mm']<-2200)
    return result


def weights(incoming):
    _,gid,count=np.unique(incoming,axis=0,return_inverse=True,return_counts=True)
    return 1/count[gid]
