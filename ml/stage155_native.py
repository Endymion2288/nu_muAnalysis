"""Frozen train-only native cluster/track spatial pilot; HTCondor only."""
import argparse
import csv
import gzip
import json
import math
import resource
import time
from pathlib import Path

import numpy as np
import ROOT
from AthenaPython import PyAthena
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from FaserActsKalmanFilter.MergeTracksConfig import MergeTrackCfg

OUT = Path('workbook/stage155_energy_ml')
CACHE = Path('ntuples/energy_ml_stage155')
plan = json.loads((OUT/'protocol.json').read_text())
requests = json.loads(Path(plan['input_native_request']).read_text())['requests']
source = requests[plan['input_request_index']]
assert source['rec'] == plan['expected_REC'] and source['origin'] == 55
phase = argparse.ArgumentParser()
phase.add_argument('phase', choices=['pilot', 'full'])
phase = phase.parse_args().phase
cases = sorted((row for row in source['cases'] if row['role'] == 1), key=lambda row: row['entry'])[:4 if phase == 'pilot' else 40]
cpu, tick = time.process_time(), time.perf_counter()
if not cases:
    (OUT/f'{phase}_summary.json').write_text(json.dumps(dict(passed=True, N=0, native_support=False,
        reason='No role1 support in frozen request0; no substitute source', new_G4=0, fits=0))+'\n')
    raise SystemExit(0)
from stage155_schema import inspect as inspect_schema
schema = inspect_schema(source['rec'])
(OUT/f'{phase}_schema.json').write_text(json.dumps(schema, indent=2)+'\n')
if not schema['verified']:
    with gzip.open(CACHE/f'{phase}.json.gz', 'wt') as stream:
        json.dump(dict(records=[], QA=[], requested_identities=[{k: r[k] for k in ['row','entry','run','event','role']} for r in cases]), stream)
    summary = dict(passed=True, phase=phase, N=0, requested_parent_N=len(cases), schema_verified=False,
        native_support=False, leading_identity_known_N=0, exact_old_count_N=0,
        same_process_first_parent_repeat=None, event_CPU_s=[],
        stop_reason='Actual relevant track persistence schema not established; frozen implementation stopped before native events.',
        CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
        ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()), RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        new_G4=0, fits=0, reserved_forward=0, overall_complete=False)
    (OUT/f'{phase}_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print('SCHEMA_STOP', schema, summary, flush=True)
    raise SystemExit(0)
manifest = list(csv.DictReader(Path('ml/configs/low_energy_files.tsv').open(), delimiter='\t'))
phys_path = manifest[source['source_index']]['input']
phys_file = ROOT.TFile.Open(phys_path)
assert phys_file and not phys_file.IsZombie()
phys_tree = phys_file.Get('nt')
branches = ['run', 'eventID', 'longTracks', 'SpacePoints', 'Track_pz0']+[f'nClusters{s}' for s in range(4)]
phys_tree.SetBranchStatus('*', 0)
for branch in branches:
    assert phys_tree.GetBranch(branch), branch
    phys_tree.SetBranchStatus(branch, 1)
records, qa = [], []
station_keys = ['clusters', 'leadingOwned', 'nonleading', 'offMeasuredWafer', 'onMeasuredWafer',
                'measuredWafers', 'eligibleWafers', 'duplicateAnchors', 'eligibleCandidates',
                'candidateSurfaceMismatch', 'unusableAnchorCandidates',
                'candidateMissingElement', 'candidateInvalidRDO', 'candidateInvalidLocal', 'candidateRoundtripFailure']


def finite_json(value):
    """Preserve typed missing measurements without inventing numeric replacements."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: finite_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(item) for item in value]
    return value


def snapshot(result):
    stations = [{key: int(getattr(s, key)) for key in station_keys} for s in result.stations]
    anchors = [dict(station=int(a.station), dimension=int(a.dimension), parameter_key=int(a.key),
        wafer=str(a.wafer), linked=bool(a.linked), identifier_equal=bool(a.identifierEqual),
        measurement=bool(a.measurement), outlier=bool(a.outlier), measurement_detector_same=bool(a.measurementDetectorSame),
        valid=bool(a.valid), normal_mm=float(a.normal_mm), state_locX_mm=float(a.stateLocal),
        exact_float32=bool(a.exactFloat32), plane_compatible=bool(a.planeCompatible),
        normal_min_mm=float(a.normalMin), normal_max_mm=float(a.normalMax), normal_arithmetic_margin_mm=float(a.normalMargin),
        state_locX_min_mm=float(a.stateLocalMin), state_locX_max_mm=float(a.stateLocalMax),
        state_roundtrip_mm=float(a.stateRoundtrip_mm), PRD_roundtrip_mm=float(a.PRDRoundtrip_mm),
        global_position_mm=list(a.globalPosition), wafer_local_position_mm=list(a.local), transform=list(a.transform)) for a in result.anchors]
    candidates = [dict(station=int(c.station), wafer=str(c.wafer), identifier=str(c.identifier),
        other_track_owners=int(c.otherTrackOwners), cluster_locX_mm=float(c.clusterLocal),
        state_locX_mm=float(c.stateLocal), dx_mm=float(c.dx_mm), dot_dx_mm=float(c.dotDx_mm),
        dx_min_mm=float(c.dxMin_mm), dx_max_mm=float(c.dxMax_mm),
        roundtrip_mm=float(c.roundtrip_mm), global_position_mm=list(c.globalPosition)) for c in result.candidates]
    return finite_json(dict(leading_index=int(result.leadingIndex), long_tracks=int(result.longTracks),
        pz0_GeV=float(result.leadingPz_GeV), stations=stations, anchors=anchors, candidates=candidates))


def summarize(v, case, identity):
    for anchor in v['anchors']:
        if len(anchor['global_position_mm']) != 3:
            continue
        g = np.array(anchor['global_position_mm'])
        f = g.astype(np.float32)
        assert anchor['exact_float32'] == bool(np.array_equal(g, f.astype(np.float64)))
        transform = np.array(anchor['transform']).reshape(4, 4)
        n, x = transform[:3, 2], transform[:3, 0]
        lo = (np.nextafter(f, np.float32(-np.inf)).astype(np.float64)+f.astype(np.float64))/2-g
        hi = (np.nextafter(f, np.float32(np.inf)).astype(np.float64)+f.astype(np.float64))/2-g
        lower = anchor['normal_mm']+np.minimum(n*lo, n*hi).sum()
        upper = anchor['normal_mm']+np.maximum(n*lo, n*hi).sum()
        margin = 64*np.finfo(np.float64).eps*max(1, np.abs(n*g).sum()+np.abs(n*transform[:3, 3]).sum())
        assert math.isclose(lower, anchor['normal_min_mm'], rel_tol=0, abs_tol=1e-12)
        assert math.isclose(upper, anchor['normal_max_mm'], rel_tol=0, abs_tol=1e-12)
        assert math.isclose(margin, anchor['normal_arithmetic_margin_mm'], rel_tol=2e-14, abs_tol=1e-20)
        assert anchor['plane_compatible'] == bool(anchor['exact_float32'] and lower-margin <= 0 <= upper+margin)
        assert abs(float(np.dot(n, g-transform[:3, 3]))-anchor['normal_mm']) <= 1e-8
        for key, value in [('state_locX_min_mm', anchor['state_locX_mm']+np.minimum(x*lo, x*hi).sum()),
                           ('state_locX_max_mm', anchor['state_locX_mm']+np.maximum(x*lo, x*hi).sum())]:
            assert math.isclose(anchor[key], value, rel_tol=0, abs_tol=1e-12)
    by_wafer = {a['wafer']: a for a in v['anchors'] if a['valid']}
    for row in v['candidates']:
        anchor = by_wafer[row['wafer']]
        transform = np.array(anchor['transform']).reshape(4, 4)
        python_dot = float(np.dot(transform[:3, 0], np.array(row['global_position_mm'])-anchor['global_position_mm']))
        assert math.isclose(python_dot, row['dx_mm'], rel_tol=0, abs_tol=1e-8)
        assert math.isfinite(row['dx_mm']) and math.isclose(row['dx_mm'], row['dot_dx_mm'], rel_tol=0, abs_tol=1e-8)
        assert row['roundtrip_mm'] <= 1e-8
        assert row['dx_min_mm'] <= row['dx_mm'] <= row['dx_max_mm']
    features = []
    for station, counts in enumerate(v['stations']):
        values = np.array([row['dx_mm'] for row in v['candidates'] if row['station'] == station])
        assert len(values) == counts['eligibleCandidates']
        assert counts['clusters'] == counts['leadingOwned']+counts['nonleading']
        assert counts['nonleading'] == counts['offMeasuredWafer']+counts['onMeasuredWafer']
        assert counts['onMeasuredWafer'] == sum(counts[k] for k in ['eligibleCandidates', 'candidateSurfaceMismatch',
            'candidateInvalidLocal', 'candidateRoundtripFailure', 'unusableAnchorCandidates', 'candidateMissingElement', 'candidateInvalidRDO'])
        available = identity and counts['eligibleWafers'] > 0
        defined = available and len(values) > 0
        features.append(dict(station=station, **counts, available=available,
            candidate_N=counts['eligibleCandidates'] if available else None,
            mean_abs_dx_mm=float(np.mean(np.abs(values))) if defined else None,
            min_abs_dx_mm=float(np.min(np.abs(values))) if defined else None,
            max_abs_dx_mm=float(np.max(np.abs(values))) if defined else None,
            RMS_dx_mm=float(np.sqrt(np.mean(values**2))) if defined else None,
            eligible_surface_fraction=counts['eligibleWafers']/counts['measuredWafers'] if identity and counts['measuredWafers'] else None,
            candidate_coverage_fraction=counts['eligibleCandidates']/counts['nonleading'] if identity and counts['nonleading'] else None))
    anchors = v['anchors']
    def maximum(key):
        return max((abs(a[key]) for a in anchors if a[key] is not None), default=None)
    return dict(row=case['row'], entry=case['entry'], run=case['run'], event=case['event'], role=1,
        pz0_GeV=v['pz0_GeV'] if identity else None, leading_identity_known=identity, long_tracks=v['long_tracks'],
        stations=features, anchor_counts=dict(total=len(anchors), linked=sum(a['linked'] for a in anchors),
            identifier_equal=sum(a['identifier_equal'] for a in anchors), measurement=sum(a['measurement'] for a in anchors),
            measurement_detector_same=sum(a['measurement_detector_same'] for a in anchors),
            valid=sum(a['valid'] for a in anchors), dimension2_key3=sum(a['dimension'] == 2 and a['parameter_key'] == 3 for a in anchors),
            old_strict_off_plane=sum(a['normal_mm'] is not None and abs(a['normal_mm']) > 1e-6 for a in anchors),
            exact_float32=sum(a['exact_float32'] for a in anchors), plane_compatible=sum(a['plane_compatible'] for a in anchors)),
        max_abs_normal_mm=maximum('normal_mm'), max_state_roundtrip_mm=maximum('state_roundtrip_mm'),
        max_PRD_roundtrip_mm=maximum('PRD_roundtrip_mm'),
        max_normal_arithmetic_margin_mm=maximum('normal_arithmetic_margin_mm'),
        max_normal_interval_width_mm=max((a['normal_max_mm']-a['normal_min_mm'] for a in anchors), default=None),
        max_state_locX_interval_width_mm=max((a['state_locX_max_mm']-a['state_locX_min_mm'] for a in anchors), default=None),
        max_candidate_dx_interval_width_mm=max((c['dx_max_mm']-c['dx_min_mm'] for c in v['candidates']), default=None),
        independent_dx_max_delta_mm=max((abs(c['dx_mm']-c['dot_dx_mm']) for c in v['candidates']), default=None),
        max_candidate_roundtrip_mm=max((c['roundtrip_mm'] for c in v['candidates']), default=None))


class Capture(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        ROOT.gInterpreter.AddIncludePath(str(Path('ml').resolve()))
        assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n'+Path('ml/stage155_native.hxx').read_text())
        return PyAthena.StatusCode.Success

    def execute(self):
        start = time.process_time()
        store, detector = PyAthena.py_svc('StoreGateSvc'), PyAthena.py_svc('DetectorStore')
        case = cases[len(records)]
        info = store.retrieve('xAOD::EventInfo', 'EventInfo')
        assert (int(info.runNumber()), int(info.eventNumber())) == (case['run'], case['event'])
        assert phys_tree.GetEntry(case['entry']) > 0
        assert (int(phys_tree.run), int(phys_tree.eventID)) == (case['run'], case['event'])
        clusters = store.retrieve('Tracker::FaserSCT_ClusterContainer', 'SCT_ClusterContainer')
        tracks = store.retrieve('TrackCollection', 'CKFTrackCollectionMergeWithoutIFT')
        points = store.retrieve('FaserSCT_SpacePointContainer', 'SCT_SpacePointContainer')
        raw = store.retrieve('FaserSCT_RDO_Container', 'SCT_RDOs')
        helper = detector.retrieve('FaserSCT_ID', 'FaserSCT_ID')
        old = ROOT.Stage124.summarize(clusters, points, tracks, raw, helper)
        assert list(old.clusters) == [int(getattr(phys_tree, f'nClusters{s}')) for s in range(4)]
        assert old.sp == int(phys_tree.SpacePoints) and old.longTracks == int(phys_tree.longTracks)
        v = snapshot(ROOT.Stage155.summarize(clusters, tracks, helper))
        assert v['long_tracks'] == old.longTracks
        assert [s['clusters'] for s in v['stations']] == list(old.clusters)
        assert v['pz0_GeV'] == finite_json(float(old.leadingPz))
        identity = v['pz0_GeV'] is not None and math.isclose(v['pz0_GeV'], case['pz'], rel_tol=3e-7, abs_tol=3e-5)
        phys_pz = max(list(phys_tree.Track_pz0), default=float('nan'))/1000
        assert math.isclose(phys_pz, case['pz'], rel_tol=3e-7, abs_tol=3e-5)
        record = summarize(v, case, identity)
        if not records:
            assert snapshot(ROOT.Stage155.summarize(clusters, tracks, helper)) == v
            record['same_process_native_repeat_exact'] = True
        if len(qa) < 4:
            qa.append(dict(row=case['row'], entry=case['entry'], run=case['run'], event=case['event'],
                anchors=v['anchors'][:4], candidates=v['candidates'][:8]))
        record['old_counts_exact'] = True
        record['execute_CPU_s'] = time.process_time()-start
        records.append(record)
        print('PARENT', len(records), case['entry'], record['anchor_counts'], flush=True)
        return PyAthena.StatusCode.Success


flags = initConfigFlags()
flags.Input.Files = [source['rec']]
flags.Input.isMC = True
flags.IOVDb.DatabaseInstance = 'OFLP200'
flags.Input.ProjectName = 'data21'
flags.GeoModel.FaserVersion = 'FASERNU-04'
flags.IOVDb.GlobalTag = 'OFLCOND-FASER-06'
flags.Detector.GeometryFaserSCT = True
flags.Concurrency.NumThreads = 0
flags.Exec.MaxEvents = len(cases)
flags.Exec.OutputLevel = 4
flags.lock()
acc = MainServicesCfg(flags)
acc.merge(PoolReadCfg(flags))
acc.merge(MergeTrackCfg(flags))
left, excluded = 0, []
for case in cases:
    entry = case['entry']
    if left < entry:
        excluded.append(f'{left+1}-{entry}')
    left = entry+1
if left < source['parent_N']:
    excluded.append(f'{left+1}-{source["parent_N"]}')
acc.getService('EventSelector').SkipEventRanges = ','.join(excluded)
acc.addEventAlgo(Capture('Stage155NativeSpatialSeparation'))
assert acc.run(maxEvents=len(cases)).isSuccess()
assert len(records) == len(cases)
phys_file.Close()
with gzip.open(CACHE/f'{phase}.json.gz', 'wt') as stream:
    json.dump(dict(records=records, QA=qa), stream, separators=(',', ':'), allow_nan=False)
summary = dict(passed=True, schema_verified=schema['verified'], phase=phase, N=len(records), selected_input_role=1, request_index=0,
    REC=source['rec'], PHYS=phys_path, original_PHYS_branches=branches,
    geometry='FASERNU-04', conditions='OFLCOND-FASER-06', configured_tracker_only=True,
    native_support=any(s['available'] and s['eligibleCandidates'] for r in records for s in r['stations']),
    leading_identity_known_N=sum(r['leading_identity_known'] for r in records),
    exact_old_count_N=sum(r['old_counts_exact'] for r in records),
    same_process_first_parent_repeat=records[0]['same_process_native_repeat_exact'],
    CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
    ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()), RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    event_bytes=(CACHE/f'{phase}.json.gz').stat().st_size,
    event_CPU_s=[r['execute_CPU_s'] for r in records], calibrated_association_probability=False, calibrated_pull=False, new_G4=0, fits=0,
    reserved_forward=0, overall_complete=False)
assert summary['event_bytes'] <= plan['resources']['final_event_bytes_cap']
(OUT/f'{phase}_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print('SUMMARY', summary, flush=True)
