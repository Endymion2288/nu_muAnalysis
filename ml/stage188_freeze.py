"""Freeze a bounded native IFT prediction experiment from existing text manifests."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage188_energy_ml'
PIN = 'd32b0ff3cc4a2dad4abfb1474a82422c3c25b305'


def main():
    OUT.mkdir(exist_ok=True)
    (ROOT / 'ntuples/energy_ml_stage188').mkdir(exist_ok=True)
    assert not (OUT / 'protocol.json').exists()
    old = json.loads((ROOT / 'workbook/stage129_energy_ml/extraction_contract.json').read_text())
    mu = Path('/eos/experiment/faser/sim/mc24/particle_gun/100012/rec/s0012-r0023/FaserMC-MC24_PG_muon_fasernu_100GeV-100012-00000-00004-s0012-r0023-xAOD.root')
    sources = [dict(label='MC100012', rec=str(mu), phys=str(mu).replace('/rec/', '/phy/').replace('-xAOD.root', '-PHYS.root'),
                    cases=[dict(entry=i, role='muon_control') for i in range(64)], component='muon', index=-1)]
    for i in (0, 48, 113):
        s = old['requests'][i]
        cases = [c for c in s['cases'] if c['role'] == 1][:32]
        sources.append(dict(label=f'{s["component"]}_{i}', index=i, rec=s['rec'], phys=s['phys'],
                            component=s['component'], cases=cases))
    assert all(Path(s['rec']).exists() and Path(s['phys']).exists() for s in sources)
    files = [
        'Tracking/Acts/FaserActsKalmanFilter/src/CreateTrkTrackTool.cxx',
        'Tracking/Acts/FaserActsKalmanFilter/src/KalmanFitterTool.cxx',
        'Tracking/Acts/FaserActsGeometry/src/FaserActsExtrapolationTool.cxx',
        'Tracking/Acts/FaserActsGeometry/src/FaserActsExtrapolationTool.h',
        'Tracking/Acts/FaserActsGeometry/src/FaserActsDetectorElement.cxx',
    ]
    snapshots = {}
    for name in files:
        snapshots[name] = subprocess.check_output(['git', '-C', str(ROOT.parent / 'calypso'), 'show', PIN + ':' + name], text=True)
    current = snapshots[files[0]].split('CreateTrkTrackTool::ConvertActsTrackParameterToATLAS', 1)[1]
    historical = subprocess.check_output(['git', '-C', str(ROOT.parent / 'calypso'), 'show', '6d6ab70b:' + files[0]], text=True).split('CreateTrkTrackTool::ConvertActsTrackParameterToATLAS', 1)[1]
    assert current == historical
    (OUT / 'pinned_source_evidence.json').write_text(json.dumps(dict(pin=PIN, converter_6d6_d32_exact=True, sources=snapshots), indent=2) + '\n')
    protocol = dict(stage=188, starting_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        question='Do actual withoutIFT leading predictions constrain unused IFT measurements, with physical field/material transport, native 1D axes, full error and all association candidates retained?',
        research_inputs=['workbook/2026-11-08_stage187_post-readout-research-roadmap.md', 'workbook/2026-11-08_stage187_electronic-only-observables-research.md'],
        sources=sources, pilot_per_source=4, full_muon_N=64, full_nu_per_source=32,
        selection='Original first train entries from fixed pi/K/charm sources0/48/113; original MC100012 control prefix0:64. Pilot first4 per source overlaps full and is not independent N. Never replace a missing/failed leading or take new reserved/isolation parents.',
        native_collection='CKFTrackCollectionMergeWithoutIFT',
        covariance_basis='Pinned converter copies ACTS surface-bound5x5 into a Trk curvilinear object without a local-frame Jacobian. Never interpret it as arbitrary curvilinear covariance. Only invert this exact representation at a TSOS carrying the same first TrackParameters pointer and a real cluster wafer: actual ACTS wafer surface, original full copied5x5 and inverse MeV conversion, zero independent time cross-covariance. If first state has no identified measurement plane, leave prediction unknown. No covariance repair/inflation.',
        transport=dict(pin=PIN, geometry='FASERNU-04', conditions='OFLCOND-FASER-06', field='FASER',
                       multiple_scattering=True, energy_loss=True, target='Every actual station0 ACTS wafer surface; retain outside geometric bounds and no-cluster predictions. Bad-strip/DAQ mask unknown; do not call geometry-only absence a certified detector hole.',
                       direction='backward', path_limit_mm=4000),
        measurement='All station0 clusters on each actual wafer; localPosition.x mm and native localCovariance(0,0) mm2. r=u-predloc0; S=V+Cpred00. Retain raw values and invalid status; all candidates, not minimum-pull selection. Store strip identifiers for shared-resource audits. SDO contributor links are diagnostics only, never deployment inputs.',
        controls='Actual source PHYS run/event and leading float32 pz0 identity; original first-state/measurement identity; no station0 in leading fit. Propagate to source wafer for source-state roundtrip. Recover ACTS surface position from copied global state, compare local axis native geometry. Compare original and zero-material transport as a fixed diagnostic, not a tuned physics correction.',
        output='Compact native initial full5x5, actual wafer transform/bounds, per-wafer prediction and variance, all candidates/strips/SDO contributor IDs if actually stored; no xAOD/ROOT persistence.',
        analysis='Fixed per-source coverage/unknown/no-cluster/multiple-candidate fractions and residual/pull summaries. If SDO genuine leading contributors exist, compare all genuine and wrong candidate distributions without picking nearest. No calibrated association posterior or coverage claim without truth/independent real-control support. No E_nu energy improvement claim from this small train pilot.',
        admission='Pilot must produce nonempty independently held-out station0 predictions and candidates on >=1 matched muon and >=1 matched nu parent, no station0 in fit, exact original pz interface, source-plane representation closure. Full CPU projection3*(max complete initialization +160*max postfirst per-event CPU) <=3000 and used pilot+projection+600<=4800; peak RSS*1.25<=12000MB; no automatic larger sample or budget.',
        resources=dict(CPU_budget_s=4800, phase_CPU_s=dict(pilot=1200, full=3000, audit=600), request_CPUs=4, memory_MB=12000, MaxRuntime_s=86400, max_live_jobs=1, inner_threads=1, final_event_bytes_cap=16777216),
        new_G4=0, new_digi=0, new_reco=0, new_energy_fits=0, new_energy_forward=0,
        invariant='Stage87/K/pz>50GeV/all roles/reserved/isolation/8strata3tails/all original gates unchanged. pz0-only first-power momentum, allowed px/py/qop/bending; signed raw and typed missing; no bad-status timing. Former8/63/2 missing surfaces remain historical unknown, not replaced by these source pilots.',
        promotion=False, overall_complete=False)
    (OUT / 'protocol.json').write_text(json.dumps(protocol, indent=2) + '\n')
    print('Frozen Stage188: pilot16 / full160; 4800 CPU s; no G4/reconstruction/fit')


if __name__ == '__main__':
    main()
