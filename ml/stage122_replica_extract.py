"""Native candidate X for selected and failed parents; nominal cuts remain intact."""
import argparse
import json
from pathlib import Path

import awkward as ak
import numpy as np
import uproot
import yaml

from extract_alternative_support import extract
from stage112_selection import BRANCHES,derive,active_cuts


def main():
    p=argparse.ArgumentParser();p.add_argument('index',type=int);p.add_argument('input');p.add_argument('output');a=p.parse_args()
    root=Path(__file__).resolve().parents[1];out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    contract=json.loads((root/'workbook/stage122_energy_ml/replica_contract.json').read_text());source=contract['sources'][a.index]
    with uproot.open(a.input) as f:
        tree=f['nt'];v=tree.arrays([k for k in BRANCHES if k in tree])
        if 'truth_barcode' not in v.fields:v=ak.with_field(v,ak.ones_like(v.truth_pdg,dtype=float)*np.nan,'truth_barcode')
        assert tree.num_entries==len(source['cases'])
        np.testing.assert_array_equal(ak.to_numpy(v.eventID),[c['event'] for c in source['cases']])
        d,flags=derive(v)
        np.testing.assert_array_equal(d['incoming'].astype('float32'),np.asarray([c['incoming'] for c in source['cases']],dtype='float32'))
    config=root/'AnalysisZipFramework/config/ml_low_energy_cuts.yaml';original=config.read_text();cfg=yaml.safe_load(original)
    active=active_cuts(cfg);scint=['Preshower Charge > 2.5 pC','VetoNu0 reduced charge < 30 pC','VetoNu1 reduced charge < 30 pC']
    nominal=np.logical_and.reduce([flags[n][0] for n,_ in active]);other=np.logical_and.reduce([flags[n][0] for n,_ in active if n not in scint])
    # Only the immutable worker copy is edited. This is a diagnostic superset,
    # not a change to production analysis cuts or to the original active cohort.
    cfg['Cuts']={k:v for k,v in cfg['Cuts'].items() if k not in scint}
    try:
        config.write_text(yaml.safe_dump(cfg,sort_keys=False));extract(0,Path(a.input),out/'candidates.npz',source=dict(run=source['run']))
    finally:config.write_text(original)
    with np.load(out/'candidates.npz') as z:candidates={k:z[k] for k in z.files if k!='metadata_json'}
    np.testing.assert_array_equal(candidates['input_entry'],np.flatnonzero(other))
    from audited_features import configuration
    payload=json.loads((out/'payload.json').read_text());assert payload['resolved']=='WAVE-Calibration-03-LG'
    refs={tag:np.array([next(r['charge_ref'] for r in rows if r['channel']==j) for j in range(4)]) for tag,rows in payload['payloads'].items()}
    names=configuration()['features'];cols=[names.index(f'ML_calo{j}_E_EM_GeV') for j in range(4)]
    candidates['x'][:,cols]=(candidates['x'][:,cols].astype(float)*refs['WAVE-Calibration-03-LG']/refs['WAVE-Calibration-01-LG']).astype('float32')
    candidates['x'][:,names.index('ML_calo_total_E_EM_GeV')]=np.sum(candidates['x'][:,cols].astype(float),axis=1).astype('float32')
    np.savez_compressed(out/'candidates.npz',**candidates)
    np.savez_compressed(out/'paths.npz',entry=np.array([c['entry'] for c in source['cases']]),nominal=nominal,other=other,
                        incoming=d['incoming'],E=d['E'],y=d['y'],pz=d['pz'],
                        **{k:d[k] for k in ['VetoNu0_reduced_charge','VetoNu1_reduced_charge','Preshower0_charge','Preshower1_charge']})
    (out/'validation.json').write_text(json.dumps(dict(parent_N=len(nominal),nominal_selected_N=int(nominal.sum()),other_cuts_N=int(other.sum()),candidate_N=len(candidates['x']),nominal_cuts_unchanged=True,only_worker_shadow_config=True),indent=2)+'\n')


if __name__=='__main__':main()
