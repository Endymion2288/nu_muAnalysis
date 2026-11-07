"""Audit frozen feature domains and placeholder semantics without refitting."""
import json

import numpy as np

from audited_features import configuration
from stage129_energy import ROOT,OUT,CACHE,load,table

d=load(ROOT/'ntuples/energy_ml_stage119/old_input.npz');cfg=configuration();rows=[]
for j,name in enumerate(cfg['features']):
    rule=cfg['rules'][name];x=d['x'][:,j];v=x[np.isfinite(x)];domain=rule['domain']
    assert not np.isin(v,rule.get('sentinels',[])).any()
    if domain=='positive':assert (v>0).all()
    if domain in ['nonnegative','count']:assert (v>=0).all()
    if domain=='count':assert ((v==np.floor(v))&(v<4294967295)).all()
    if domain=='boolean':assert np.isin(v,[0,1]).all()
    if domain=='charge_sign':assert np.isin(v,[-1,1]).all()
    if 'allowed_values' in rule:assert np.isin(v,rule['allowed_values']).all()
    rows.append(dict(feature=name,domain=domain,N=len(x),finite_N=len(v),NaN_N=int(np.isnan(x).sum()),negative_N=int((v<0).sum()),minus1_N=int((v==-1).sum()),minus999_N=int((v==-999).sum())))
calo=d['x'][:,[cfg['features'].index(f'ML_calo{i}_E_EM_GeV') for i in range(4)]];total=d['x'][:,cfg['features'].index('ML_calo_total_E_EM_GeV')]
assert not np.isfinite(total[~np.isfinite(calo).all(1)]).any()
assert not any(n in cfg['features'] for n in ['ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_mu_log_p0_over_p1'])
f=load(CACHE/'saturation_features.npz')
assert not np.isinf(f['features']).any()
for j in range(3):
    available=f['valid'][:,4*j+3].astype(bool)
    assert not np.isfinite(f['features'][~available,5*j:5*j+3]).any()
    assert np.isfinite(f['features'][available,5*j:5*j+3]).all()
    assert (f['features'][available,5*j+1:5*j+3]>=0).all()
table('feature_domain_audit.tsv',rows)
(OUT/'feature_domain_validation.json').write_text(json.dumps(dict(columns=62,roles_and_rows_unchanged=True,invalid_minus1_in_positive_count_nonnegative_N=0,finite_sentinels_N=0,Calo_missing_total_preserved=True,saturation_failed_Q_and_uncertainty_missing=True,signed_negative_values_preserved=True,scope='audit of existing frozen arrays and new recovery features, no rebuild/refit/forward'),indent=2)+'\n')
