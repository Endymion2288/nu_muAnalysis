"""Original native selection/typed62 and exact sparse parent identity closure."""
import argparse
import json
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

from audited_features import configuration
from extract_alternative_support import extract

p=argparse.ArgumentParser();p.add_argument('code');p.add_argument('index',type=int);p.add_argument('input');p.add_argument('output');a=p.parse_args()
root=Path(a.code);contract=json.loads((root/'workbook/stage119_energy_ml/production_contract.json').read_text());request=contract['requests'][a.index];source=request['source'];out=Path(a.output)
with uproot.open(a.input) as f:
    tree=f['nt'];assert tree.num_entries==len(request['entries'])
    v=tree.arrays(['run','eventID','truth_pdg','truth_px','truth_py','truth_pz','Track_pz0','Track_isForward'])
    np.testing.assert_array_equal(ak.to_numpy(v.eventID),request['eventID']);assert np.all(ak.to_numpy(v.run)==source['run'])
    incoming=np.column_stack([ak.to_numpy(ak.firsts(v['truth_'+k])) for k in ['pdg','px','py','pz']]);np.testing.assert_array_equal(incoming,request['incoming'])
    identity=dict(parent_N=request['parent_N'],reconstructed_N=tree.num_entries,exact_run_event_incoming=True,
        all_sparse_entries_retained=True,forward_tracks=int(ak.sum(v.Track_isForward)),track_N=int(ak.sum(ak.num(v.Track_pz0))))
    c=tree.arrays([f'Calo{j}_{k}' for j in range(4) for k in ['charge','E_EM','status']],library='np')
payload=json.loads((out/'payload.json').read_text());assert payload['resolved']=='WAVE-Calibration-03-LG'
refs={tag:np.array([next(r['charge_ref'] for r in rows if r['channel']==j) for j in range(4)]) for tag,rows in payload['payloads'].items()}
calibration=[]
for j in range(4):
    q,e,status=[c[f'Calo{j}_{k}'] for k in ['charge','E_EM','status']];use=(status==0)&np.isfinite(q+e)&(abs(q)>1e-6)
    if use.any():np.testing.assert_allclose(e[use]/q[use],330/refs['WAVE-Calibration-03-LG'][j],rtol=2e-6)
    calibration.append(dict(module=j,N=int(use.sum())))
extract(0,Path(a.input),out/'native_selected.npz',source=source)
with np.load(out/'native_selected.npz') as z:data={k:z[k] for k in z.files if k!='metadata_json'};md=json.loads(str(z['metadata_json']))
# Payload-only representation conversion once, retaining the native formula QA.
names=configuration()['features'];cols=[names.index(f'ML_calo{j}_E_EM_GeV') for j in range(4)]
data['x'][:,cols]=(data['x'][:,cols].astype(float)*refs['WAVE-Calibration-03-LG']/refs['WAVE-Calibration-01-LG']).astype('float32')
data['x'][:,names.index('ML_calo_total_E_EM_GeV')]=np.sum(data['x'][:,cols].astype(float),axis=1).astype('float32')
data['sparse_entry']=data['input_entry'].copy();data['input_entry']=np.asarray(request['entries'])[data['sparse_entry']]
md.update(parent_identity=identity,calibration=calibration,reference='WAVE-Calibration-01-LG',conversion='actual per-run COOL payload ratio once; no truth/residual scale')
np.savez_compressed(out/'selected.npz',**data,metadata_json=np.array(json.dumps(md)))
(out/'native_selected.npz').unlink();(out/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
with np.load(out/'selected.npz') as z:
    for k,v in data.items():np.testing.assert_array_equal(z[k],v)
