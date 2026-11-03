#!/usr/bin/env python3
"""Independently validate delivered stage70 identities, raw inputs and payload algebra."""
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np

from audited_features import configuration, SCINTILLATORS, WAVE_INVALID, clean


def main():
    root=Path(__file__).resolve().parents[1];out=root/'workbook/stage70_energy_ml'
    start=time.perf_counter();cpu_start=time.process_time();cfg=configuration();names=cfg['features']
    with np.load(root/'ntuples/energy_ml_stage70/support.npz') as z:
        data={k:z[k] for k in z.files if k!='metadata_json'};md=json.loads(str(z['metadata_json']))
    with np.load(root/'ntuples/energy_ml_stage55/dataset.npz') as z:
        oldkeys=set(map(tuple,z['incoming']))
    keys=list(map(tuple,data['incoming']));mask=data['new_training_support'];newkeys=[k for k,m in zip(keys,mask) if m]
    assert len(newkeys)==len(set(newkeys)) and not set(newkeys)&oldkeys
    assert set(newkeys)==set(keys)-oldkeys
    c=[names.index(f'ML_calo{j}_E_EM_GeV') for j in range(4)];total=names.index('ML_calo_total_E_EM_GeV');other=[i for i in range(62) if i not in c+[total]]
    np.testing.assert_array_equal(data['x'][:,other],data['x_produced'][:,other])
    conditions=json.loads((out/'calo_conditions_qa.json').read_text())
    for run in np.unique(data['run']):
        rows={tag:next(r['rows'] for r in conditions['measurements'] if r['tag']==tag and r['run']==run) for tag in ['WAVE-Calibration-01-LG','WAVE-Calibration-03-LG']}
        for j,col in enumerate(c):
            q={tag:next(r['payload']['charge_ref'] for r in rr if r['channel']==j) for tag,rr in rows.items()}
            take=data['run']==run
            expected=(data['x_produced'][take,col].astype(float)*q['WAVE-Calibration-03-LG']/q['WAVE-Calibration-01-LG']).astype('float32')
            np.testing.assert_array_equal(data['x'][take,col],expected)
    np.testing.assert_array_equal(data['x'][:,total],np.sum(data['x'][:,c].astype(float),axis=1).astype('float32'))
    assert np.array_equal(np.isnan(data['x']),np.isnan(data['x_produced']))
    for j,det in enumerate(SCINTILLATORS):
        raw=data['raw_charge'][:,j].astype('float32');raw[((data['status'][:,j].astype(int)&WAVE_INVALID)!=0)|~np.isfinite(raw)]=np.nan
        np.testing.assert_array_equal(data['x'][:,names.index(det+'_raw_charge')],raw)
    assert names[0]=='ML_mu_pz0_GeV'
    for forbidden in ['LeadTrack_p0','LeadTrack_p1','LeadTrack_pz1','ML_mu_p_GeV']:
        assert forbidden not in names
    np.testing.assert_array_equal(clean([-999,-1,0,1],dict(domain='nonnegative')),[np.nan,np.nan,0,1])
    np.testing.assert_array_equal(clean([-999,-1,0],dict(domain='signed')),[-999,-1,0])
    summary=json.loads((out/'summary.json').read_text())
    assert summary['new_support_N']==len(newkeys)
    assert summary['new_lowE_N']['E50_100']==int((mask&(data['truth_E_GeV']>=50)&(data['truth_E_GeV']<100)).sum())
    assert summary['new_lowE_N']['E100_200']==int((mask&(data['truth_E_GeV']>=100)&(data['truth_E_GeV']<200)).sum())
    rows=list(csv.DictReader((out/'identities.tsv').open(),delimiter='\t'))
    for r in rows:
        take=np.ones(len(mask),bool) if r['component']=='all' else data['component']==r['component']
        assert int(r['selected_N'])==int(take.sum()) and int(r['new_support_N'])==int((take&mask).sum())
    record=dict(passed=True,selected_N=len(mask),new_unique_N=len(newkeys),known_key_intersection_N=0,features_unchanged_exact=57,calo_payload_conversion_exact=True,calo_sum_nan_propagation_exact=True,raw11_status_exact=True,typed_sentinels_signed_negative_preserved=True,source_and_low_energy_tables_exact=True,old_cache_writes=0,model_fits=0,F7_inference=0,wall_s=time.perf_counter()-start,CPU_s=time.process_time()-cpu_start,peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/'final_validation.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))


if __name__ == "__main__":
    main()
