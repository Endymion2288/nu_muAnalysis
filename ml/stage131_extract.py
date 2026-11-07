"""Original selected typed62 and measured selection migration for one natural parent."""
import json
import sys
from pathlib import Path
import awkward as ak
import numpy as np
import uproot
import yaml
from audited_features import configuration
from extract_alternative_support import extract
from stage112_selection import BRANCHES,derive,active_cuts

root=Path(sys.argv[1]);work=Path(sys.argv[2]);case=json.loads((work/'case.json').read_text());index=case['frame_index'];path=work/'ntuple.root';OUT=root/'workbook/stage131_energy_ml';CACHE=root/'ntuples/energy_ml_stage131'
with uproot.open(path) as f:
    t=f['nt'];a=t.arrays([b for b in BRANCHES if b in t]);assert len(a)==1
    if 'truth_barcode' not in a.fields:a=ak.with_field(a,ak.ones_like(a.truth_pdg,dtype=float)*np.nan,'truth_barcode')
    d,flags=derive(a);np.testing.assert_array_equal(d['incoming'][0].astype('float32'),np.asarray(case['incoming'],dtype='float32'))
    cfg=yaml.safe_load((root/'AnalysisZipFramework/config/ml_low_energy_cuts.yaml').read_text());decisions={n:bool(flags[n][0][0]) for n,_ in active_cuts(cfg)}
report=dict(index=index,role=case['role'],stratum=case['stratum'],identity_incoming_exact=True,selected_N=int(all(decisions.values())),cuts=decisions,reco_pz_GeV=float(d['pz'][0]),truth_E_GeV=float(d['E'][0]),prior_selected_N=1,scope='conditional response migration on frozen selected parent frame; not unbiased efficiency')
extract(0,path,CACHE/f'parent_{index}_selected.npz',source=dict(run=990131))
with np.load(CACHE/f'parent_{index}_selected.npz') as z:content={k:z[k] for k in z.files}
assert len(content['x'])==report['selected_N']
if len(content['x']):
    payload=json.loads((root/'workbook/stage129_energy_ml/fullchain_fixed_payload.json').read_text());assert payload['resolved']=='WAVE-Calibration-03-LG'
    refs={tag:np.asarray([next(x['charge_ref'] for x in r if x['channel']==j) for j in range(4)]) for tag,r in payload['payloads'].items()};names=configuration()['features'];cols=[names.index(f'ML_calo{j}_E_EM_GeV') for j in range(4)]
    content['x'][:,cols]=(content['x'][:,cols].astype(float)*refs['WAVE-Calibration-03-LG']/refs['WAVE-Calibration-01-LG']).astype('float32');content['x'][:,names.index('ML_calo_total_E_EM_GeV')]=content['x'][:,cols].astype(float).sum(1).astype('float32')
    np.savez_compressed(CACHE/f'parent_{index}_selected.npz',**content)
(OUT/f'parent_{index}_selection.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
