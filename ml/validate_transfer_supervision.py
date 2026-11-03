#!/usr/bin/env python3
"""Small feature/role QA for the new stage69 reader; never writes old artifacts."""
import json
import numpy as np
from audited_features import SCINTILLATORS,load,build,clean,configuration
from transfer_supervision import OUT,inputs,begin,resources,save

start=begin();cfg=configuration();d,s,x=load();roles=inputs();features=cfg['features']
assert len(features)==62
assert not set(features)&{'ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0'}
assert not set(features)&{n+'_charge' for n in SCINTILLATORS}
assert sum(n+'_raw_charge' in features for n in SCINTILLATORS)==11
np.testing.assert_array_equal(clean([-999,-1,0,2],dict(domain='nonnegative')),[np.nan,np.nan,0,2])
np.testing.assert_array_equal(clean([-999,-1,0,1],dict(domain='charge_sign')),[np.nan,-1,np.nan,1])
np.testing.assert_array_equal(clean([-1,0,3,2**32-1],dict(domain='count')),[np.nan,0,3,np.nan])
np.testing.assert_array_equal(clean([-999,-1,0],dict(domain='signed',sentinels=[999999])),[-999,-1,0])
# Negative values are not universally sentinels: explicit branch semantics win.
one={k:v[:1].copy() for k,v in s.items()};row=one['row'][0];names=json.loads(str(d['metadata_json']))['features']
j=names.index('ML_mu_x0_mm');original=d['x'][row,j];d['x'][row,j]=999999
assert np.isnan(build(d,one)[0,features.index('ML_track_chord_slope_x')]);d['x'][row,j]=original
one['raw_charge'][0,0]=-1.;one['status'][0,0]=48
assert build(d,one)[0,features.index('VetoNu0_raw_charge')]==-1.
one['status'][0,0]=128
assert np.isnan(build(d,one)[0,features.index('VetoNu0_raw_charge')])
one['calo_status'][0,0]=128
assert np.isnan(build(d,one)[0,features.index('ML_calo_total_E_EM_GeV')])
all_missing=np.isnan(x).any(1);assert int(all_missing.sum())==42
used=set(roles['row']);protected=[int(r) for r,m in zip(s['row'],all_missing) if m and r not in used];assert len(protected)==11
incoming={r:set(map(tuple,roles['incoming'][roles['role']==r])) for r in ['train','cal','eval']}
for a,b in [('train','cal'),('train','eval'),('cal','eval')]:assert not incoming[a]&incoming[b]
save(OUT/'policy_validation.json',dict(**resources(start),features=62,raw_scintillators=11,forbidden_linear_momenta=[],typed_nonnegative_and_count_sentinels_to_NaN=True,legal_signed_minus1_and_minus999_retained=True,geometry_sentinel_dependency_to_NaN=True,bad_fit_raw_retained_bad_waveform_raw_NaN=True,missing_calo_module_invalidates_total=True,original_missing_N=42,eligible_missing_counts=[21,3,7],protected_unused_missing_rows=protected,train_cal_eval_exact_incoming_overlap=0,old_artifacts_written=0,model_fits=0))
print('typed policy and all42 missing roles passed')
