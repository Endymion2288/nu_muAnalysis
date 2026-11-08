"""Freeze a real-data held-out IFT comparison using already certified source pairs."""
import json
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[1]
out=root/'workbook/stage190_energy_ml';out.mkdir(exist_ok=True)
assert not (out/'protocol.json').exists()
m=json.loads((root/'workbook/stage160_energy_ml/matched_manifest.json').read_text())
assert m['metadata']['/TagInfo']['GeoFaser']=='FASERNU-04'
assert m['metadata']['/TagInfo']['IOVDbGlobalTag']=='OFLCOND-FASER-05'
cases=[dict(r,entry=r['native_entry'],role='data_control') for r in m['records'][:64]]
assert len(cases)==64 and all(r['unique_pair'] for r in cases)
assert len({c['entry'] for c in cases})==64
p=dict(stage=190,starting_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    question='Do actual held-out IFT predictions on the original run15838 data source have usable support, residuals and ambiguity, compared descriptively with the separate MC controls? No data purity or calibrated association is assumed.',
    research='workbook/2026-11-08_stage187_electronic-only-observables-research.md §3/A,D',
    manifest='workbook/stage160_energy_ml/matched_manifest.json',
    source_policy='Original first64 PHYS parents with certified native entry/run/event/timestamp; pilot first4 only, no pz/quality/residual filtering or replacements. Stage161 original raw mismatch remains; no raw/scintillator claim is reopened.',
    sources=[dict(label='data15838',rec=m['REC'],phys=m['PHYS'],index=-2,component='real_data',cases=cases)],
    pilot_per_source=4,native_collection='CKFTrackCollectionBackwardWithoutIFT',
    collection_policy='Use actual backward collection fixed by historical PHYS producer and Stage161 exact4-state match, never select collection by new residuals. No new merge, fit, digitization or ntuple writer.',
    transport=dict(pin='d32b0ff3cc4a2dad4abfb1474a82422c3c25b305',geometry='FASERNU-04',conditions='OFLCOND-FASER-05',database='CONDBR3',
        field='FASER',material_map='/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/acts/material-maps-alma9.json',
        direction='backward',path_limit_mm=4000,multiple_scattering=True,energy_loss=True),
    measurement='Reuse exact gcc13 Stage188 native bridge, actual first TSOS measurement/wafer recovery, full covariance inverse copied units, all48 IFT wafers and all cluster candidates; failures retained. Same source propagation and no-material diagnostics. No nearest hit, made-up 2D strip point, detector hole, covariance inflation or truth deployment.',
    review='Fixed all-candidate residual/pull/3-sigma descriptive summaries and original matched/support/pz50-100 counts. All shared PRDs correlated. Data SDO is absent and is not filled. Cannot certify purity, genuine/wrong hit assignment or pull coverage from all-candidate counts.',
    admission='At least1 original data parent matched with recovered source and inside wafer candidates; 3*(complete pilot incl gcc compile +64*slowest postfirst execute CPU)<=600; used+projection+200<=1200; RSS*1.25<=8000MB.',
    resources=dict(CPU_budget_s=1200,phase_CPU_s=dict(pilot=400,full=600,audit=200),request_CPUs=4,memory_MB=8000,MaxRuntime_s=86400,max_live_jobs=1,final_event_bytes_cap=16777216),
    control_limit='One real run/source, not independently certified muon purity or matched pz/occupancy mixture. MC100012 only100GeV; compare support and necessary response diagnostics, never equate raw RMS with common calibrated resolution.',
    new_G4=0,new_reco=0,new_fits=0,new_energy_forward=0,reserved_predictions=0,promotion=False,overall_complete=False)
(out/'protocol.json').write_text(json.dumps(p,indent=2)+'\n')
for name in ['build_spec.json','pinned_source_evidence.json']:
    (out/name).write_bytes((root/'workbook/stage188_energy_ml'/name).read_bytes())
print('Frozen Stage190 original real-data4/64, 1200 CPU s; no reconstruction or energy fit')
