"""Compact complete-parent cost pilot result; no energy forward or fitting."""
import json,sys
from pathlib import Path
import awkward as ak
import numpy as np
import uproot
from audited_features import configuration
from extract_alternative_support import extract
from stage112_selection import BRANCHES,derive,active_cuts
import yaml
root=Path(sys.argv[1]);index=int(sys.argv[2]);path=Path(sys.argv[3]);OUT=root/'workbook/stage129_energy_ml';CACHE=root/'ntuples/energy_ml_stage129';case=json.loads((OUT/'fullchain_protocol.json').read_text())['cases'][index]
with uproot.open(path,array_cache=None) as f:
 t=f['nt'];calostatus=t.arrays([f'Calo{j}_status' for j in range(4)],library='np');a=t.arrays([b for b in BRANCHES if b in t]);N=len(a);assert N==1
 if 'truth_barcode' not in a.fields:a=ak.with_field(a,ak.ones_like(a.truth_pdg,dtype=float)*np.nan,'truth_barcode')
 d,flags=derive(a);incoming=d['incoming'][0];np.testing.assert_array_equal(incoming.astype('float32'),np.asarray(case['incoming'],dtype='float32'))
 cfg=yaml.safe_load((root/'AnalysisZipFramework/config/ml_low_energy_cuts.yaml').read_text());active=active_cuts(cfg);decisions={name:bool(flags[name][0][0]) for name,_ in active};selected=all(decisions.values())
 report=dict(index=index,EVNT=case['EVNT'],EVNT_entry=case['entry'],incoming=incoming.tolist(),identity_incoming_exact=True,ntuple_N=N,selected_N=int(selected),cuts=decisions,reco_pz_GeV=float(d['pz'][0]),truth_E_GeV=float(d['E'][0]),stratum=case['stratum'],role='engineering only; no fit/prediction',independent_training_added_N=0,calo_status={k:int(v[0]) for k,v in calostatus.items()})
extract(0,path,CACHE/f'fullchain_{index}_selected.npz',source=dict(run=990129))
with np.load(CACHE/f'fullchain_{index}_selected.npz') as z:content={k:z[k] for k in z.files}
if len(content['x']):
 payload=json.loads((OUT/f'fullchain_{index}_payload.json').read_text());assert payload['resolved']=='WAVE-Calibration-03-LG';refs={tag:np.asarray([next(x['charge_ref'] for x in r if x['channel']==j) for j in range(4)]) for tag,r in payload['payloads'].items()};names=configuration()['features'];cols=[names.index(f'ML_calo{j}_E_EM_GeV') for j in range(4)];content['x'][:,cols]=(content['x'][:,cols].astype(float)*refs['WAVE-Calibration-03-LG']/refs['WAVE-Calibration-01-LG']).astype('float32');content['x'][:,names.index('ML_calo_total_E_EM_GeV')]=content['x'][:,cols].astype(float).sum(1).astype('float32');np.savez_compressed(CACHE/f'fullchain_{index}_selected.npz',**content)
(OUT/f'fullchain_{index}_selection.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)
