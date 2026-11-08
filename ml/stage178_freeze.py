"""Freeze representation-aware S0 pilot before any scientific array access."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage178_energy_ml'
OUT.mkdir(parents=True, exist_ok=True)
(ROOT / 'ntuples/energy_ml_stage178').mkdir(parents=True, exist_ok=True)
assert not (OUT / 'protocol.json').exists()
old = json.loads((ROOT / 'workbook/stage176_energy_ml/protocol.json').read_text())
commit = 'd32b0ff3cc4a2dad4abfb1474a82422c3c25b305'
paths = {
    'Tracking/Acts/FaserActsKalmanFilter/src/CreateTrkTrackTool.cxx': ['CurvilinearParameters', 'const Amg::Vector3D& pos', 'Amg::Vector3D tmom'],
    'PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.cxx': ['trackParameters()->front()', 'm_xup.push_back', 'm_yup.push_back', 'm_zup.push_back', 'm_pxup.push_back', 'm_pyup.push_back', 'm_pzup.push_back'],
    'PhysicsAnalysis/NtupleDumper/src/NtupleDumperAlg.h': ['std::vector<double> m_xup', 'std::vector<double> m_pxup'],
}
records = []
for name, terms in paths.items():
    source = subprocess.check_output(['git', '-C', str(ROOT.parent / 'calypso'), 'show', commit + ':' + name], text=True)
    assert all(term in source for term in terms)
    records.append(dict(path=name, commit=commit, source_bytes=len(source.encode()),
        lines=[dict(line=i+1, text=line) for i, line in enumerate(source.splitlines()) if any(t in line for t in terms)]))
include = Path('/cvmfs/atlas.cern.ch/repo/sw/software/24.0/Athena/24.0.41/InstallArea/x86_64-el9-gcc13-opt/include')
for name, terms in {
    'TrkParametersBase/CurvilinearParametersT.icc': ['this->m_position = pos;', 'this->m_momentum = mom;', 'S(this->m_position, curvilinearFrame())', 'curvilinFrame(this->momentum().unit())'],
    'TrkEventPrimitives/CurvilinearUVT.icc': ['m_curvT(dir)', 'return (m_curvT);'],
    'TrkSurfaces/PlaneSurface.h': ['PlaneSurface(const Amg::Vector3D& position, const CurvilinearUVT& curvUVT)'],
}.items():
    source = (include / name).read_text()
    assert all(term in source for term in terms)
    records.append(dict(path=str(include / name), source_bytes=len(source.encode()),
        lines=[dict(line=i+1, text=line) for i, line in enumerate(source.splitlines()) if any(t in line for t in terms)]))
for name, terms in {
    'AnalysisZipFramework/config/ml_definitions.yaml': ['SafeAt(Track_px0, LeadTrack_Idx) / 1000.0', 'SafeAt(Track_x0, LeadTrack_Idx)'],
    'ml/extract_alternative_support.py': ["old_x = np.column_stack", ".astype('float32')"],
}.items():
    source = (ROOT / name).read_text()
    assert all(t in source for t in terms)
    records.append(dict(path=name, source_bytes=len(source.encode()),
        lines=[dict(line=i+1, text=line) for i, line in enumerate(source.splitlines()) if any(t in line for t in terms)]))
(OUT / 'source_semantics.json').write_text(json.dumps(dict(passed=True, records=records,
    meaning='The first fitted state is a curvilinear plane centered at fitted xyz, normal along fitted momentum. Ntuple double values become compact float32. Infer enclosing state boxes, never an exact recovered plane.'), indent=2) + '\n')
p = dict(stage=178, parent_stage=176, question='Can rounded original fitted states certify S0 sides and enable fixed G4-only birth/crossing support without another full reconstruction?',
    sources=old['sources'][:3] + ['ntuples/energy_ml_stage176/parent_50_lineage.json.gz',
        'ntuples/energy_ml_stage176/parent_50_qa_hits.json.gz', 'workbook/stage176_energy_ml/parent_50_S0.json',
        'workbook/stage176_energy_ml/process_resources.json', 'software/stage176/observer-runtime.tar.gz',
        'ml/configs/audited_features.json'],
    reference_index=50, replay_indices=old['remaining_indices'], selection=old['selection'],
    representation='Enclose each original float32 state by neighboring-float midpoints; outward double rounding throughout. Momentum cells in GeV expand for division rounding then scale to MeV. Unknown/NaN/-999/missing state remains unknown. No extra p0/p1/pz1.',
    plane='Ideal semantic sign p dot (r-center). Also enclose normalized momenta for native-normal validation; native50 actual xyz/momentum/normal must lie inside and every robust birth/step sign must agree. Crossing endpoints certified only if both signs robust; unknown endpoints preserved. No interpolation or nominal-z plane.',
    feasibility_acceptance=['pinned source semantics validated', 'native50 state and normal enclosed', 'every robust birth and primary-step endpoint agrees with actual native plane', 'both before and after robust births exist', 'all original12 and missing planes retained'],
    admission='Only after passed feasibility; threefold11*(measured successful Stage176 sim+HITScheck CPU + complete feasibility CPU) <=3000 replay allowance; plus used schedulerCPU+1200audit <=4500 total. No reconstruction or budget relaxation.',
    replay='Same exact original11 EVNT/entry/G4seed/HITSfilename/geometry/tag/physics; byte-identical Stage176 observer runtime. Preserve every old observer field and ordered HITS partition. Three independent single-thread chains on4cores. No digitization/reco/ntuple/new parents.',
    CPU_budget_s=4500, phase_CPU_allowance_s=dict(feasibility=300, replay=3000, audit=1200), request_CPUs=4,
    request_memory_MB=12000, worker_processes=3, max_jobs=1, MaxRuntime_s=86400,
    analysis='Source-resolved all-time corrected SD response and actual-step energy brackets with finite plane intervals, not DAQ analog charge, radiative loss correction or energy improvement. Missing/reselected parent remains in original denominator.',
    preserve=old['preserve'], no=['new energy fits or forward', 'extra parents', 'automatic4032 replay', 'charge add-back', 'truth deployment', 'imputed missing plane', 'crossing interpolation'],
    overall_complete=False, promotion=False)
(OUT / 'protocol.json').write_text(json.dumps(p, indent=2) + '\n')
print('FROZEN Stage178 source semantics and exact original12; no event computation')
