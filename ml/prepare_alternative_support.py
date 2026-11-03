#!/usr/bin/env python3
"""Freeze stage70 full-file extraction after the bounded, same-source native QA."""
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

from audited_features import REPO, SCINTILLATORS, WAVE_INVALID, clean, configuration

OUT = REPO/'workbook/stage70_energy_ml'


def main():
    start = time.perf_counter()
    cfg = json.loads((REPO/'ml/configs/alternative_support_pilot.json').read_text())
    schema = json.loads((OUT/'input_schema.json').read_text())
    assert schema['total_events'] == 10784 <= cfg['input_limit']['full_source_events_total_max']
    assert not (OUT/'protocol.json').exists()
    records = []
    for index, component in enumerate(['pi', 'k']):
        native = json.loads((OUT/f'native_{component}.json').read_text())
        scratch = Path('/tmp/nu_mu_stage70_qa')/component
        with np.load(scratch/'qa.npz') as z:
            md = json.loads(str(z['metadata_json']))
            assert md['features'] == configuration()['features'] and md['raw_N'] == 16
            assert z['x'].shape == (md['selected_N'], 62)
            for j,detector in enumerate(SCINTILLATORS):
                expected = z['raw_charge'][:,j].astype('float32')
                expected[(z['status'][:,j].astype(int)&WAVE_INVALID)!=0] = np.nan
                np.testing.assert_array_equal(z['x'][:,md['features'].index(detector+'_raw_charge')], expected)
            saved = {k:z[k] for k in ['run', 'eventID', 'x']}
        with uproot.open(scratch/'ntuple.root') as f:
            a = f['nt'].arrays(['run','eventID','truth_pdg','truth_px','truth_py','truth_pz','truth_m'], entry_stop=2)
            assert f['nt'].num_entries == 16
            for entry,r in enumerate(native['events']):
                assert r['run'] == int(a.run[entry]) and r['eventID'] == int(a.eventID[entry])
                assert r['incoming_pdg'] == int(a.truth_pdg[entry,0])
                np.testing.assert_array_equal(r['incoming_raw'][:3], [float(a['truth_'+axis][entry,0]) for axis in ['px','py','pz']])
            assert np.allclose(ak.to_numpy(ak.flatten(a.truth_m[abs(a.truth_pdg)==13]))/1000, .1056583755, atol=1e-7)
        validation = (scratch/'validation.txt').read_text()
        assert 'validated entries=16 branches=528' in validation
        (OUT/f'qa_{component}.json').write_text(json.dumps(dict(extraction=md, native_PHYS_incoming_exact=True,
            muon_mass_raw_MeV_to_GeV=True, reconstruction_time=(scratch/'reco.time').read_text().strip(),
            ntuple_time=(scratch/'ntuple.time').read_text().strip()), indent=2)+'\n')
        (OUT/f'qa_{component}_production.txt').write_text(validation)
        records.append(dict(component=component, raw_N=16, selected_N=md['selected_N'],
                            raw_columns=11, x_columns=62, native_PHYS_incoming_exact=True))
    np.testing.assert_array_equal(clean([-999,-1,0,1], dict(domain='nonnegative')), [np.nan,np.nan,0,1])
    np.testing.assert_array_equal(clean([-999,-1,0], dict(domain='signed')), [-999,-1,0])
    old = json.loads((OUT/'existing_phys_qa.json').read_text())
    assert 'Calo0_E_EM' in old['differing_branches']
    # Freeze the same two files. A known old PHYS has incompatible calorimeter
    # energies and detector branches, so both use the validated nominal runtime.
    protocol = dict(stage=70, frozen_utc=datetime.now(timezone.utc).isoformat(), source_contract=cfg,
                    input_events_by_source=[r['entries'] for r in schema['files']],
                    full_files=True, energy_model_fits=0, F7_inference=0, spectral_toys=0,
                    qa=records, qa_unique_RDO_entries=32, native_successful_event_visits=4,
                    native_failed_event_visits=2, total_explicit_QA_RDO_visits=38,
                    old_pi_PHYS_reuse=False, old_pi_PHYS_reason='actual Calo energy columns differ in fixed 16-event comparison; do not patch calibration',
                    resources=dict(condor_jobs=2, request_cpus=1, request_memory_MB=3000,
                                   request_disk_MB=5500, max_runtime_s=3600, max_retries=0,
                                   total_CPU_budget_s=7200, retained_bytes_budget=5000000),
                    cost_basis='actual16-event reco wall25.99/25.15s; historical stage55 full-file reco4.010events/s and ntuple20.846events/s; estimates are not measured full-file costs',
                    estimated_reco_plus_ntuple_wall_s=[784*(1/4.010+1/20.846),10000*(1/4.010+1/20.846)],
                    exclusion='all stage55 developed cache exact incoming(pdg,px,py,pz), then stable component/source/entry internal dedup; inherit protected roles; no residual selection',
                    statistical_scope='two inherited training sources; no independent confirmation or power claim; unit MC; keep all selected missing and difficult rows',
                    wall_s=time.perf_counter()-start)
    (OUT/'protocol.json').write_text(json.dumps(protocol, indent=2)+'\n')
    print(json.dumps(dict(qa=records, input_events=10784, frozen_utc=protocol['frozen_utc'])))


if __name__ == '__main__':
    main()
