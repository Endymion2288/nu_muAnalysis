"""Frozen train-only native cluster/track spatial pilot; HTCondor only."""
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

OUT = Path('workbook/stage153_energy_ml')
CACHE = Path('ntuples/energy_ml_stage153')
plan = json.loads((OUT/'protocol.json').read_text())
requests = json.loads(Path(plan['input_native_request']).read_text())['requests']
source = requests[plan['input_request_index']]
assert source['rec'] == plan['expected_REC'] and source['origin'] == 55
cases = sorted((row for row in source['cases'] if row['role'] == 1), key=lambda row: row['entry'])[:40]
cpu, tick = time.process_time(), time.perf_counter()
if not cases:
    (OUT/'native_summary.json').write_text(json.dumps(dict(passed=True, N=0, native_support=False,
        reason='No role1 support in frozen request0; no substitute source', new_G4=0, fits=0))+'\n')
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
                'candidateSurfaceMismatch', 'candidateInvalidVariance', 'unusableAnchorCandidates',
                'candidateMissingElement', 'candidateInvalidRDO']


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
    """Transient candidate data feed independent arithmetic; no full cloud saved."""
    stations = [{key: int(getattr(s, key)) for key in station_keys} for s in result.stations]
    anchors = [dict(station=int(a.station), layer=int(a.layer), side=int(a.side), wafer=str(a.wafer),
        linked=bool(a.linked), identifier_equal=bool(a.identifierEqual), measurement=bool(a.measurement),
        outlier=bool(a.outlier), dimension=int(a.dimension), parameter_key=int(a.key),
        same_surface=bool(a.sameSurface), valid=bool(a.valid), measurement_type=str(a.measurementType),
        state_type=str(a.stateType), parameter_type=str(a.parameterType),
        surface_max_element_difference=float(a.surfaceMaxDifference),
        state_loc1_mm=float(a.stateLoc1), measurement_loc1_mm=float(a.measurementLoc1),
        state_variance_mm2=float(a.stateVariance), measurement_variance_mm2=float(a.measurementVariance),
        global_roundtrip_mm=float(a.positionRoundtrip_mm), parameters=list(a.parameters), covariance=list(a.covariance),
        measurement_transform=list(a.measurementTransform), state_transform=list(a.stateTransform)) for a in result.anchors]
    candidates = [dict(station=int(c.station), layer=int(c.layer), side=int(c.side), identifier=str(c.identifier),
        wafer=str(c.wafer), other_track_owners=int(c.otherTrackOwners), cluster_loc1_mm=float(c.local),
        state_loc1_mm=float(c.stateLocal), cluster_variance_mm2=float(c.variance), state_variance_mm2=float(c.stateVariance),
        r2=float(c.r2), global_roundtrip_mm=float(c.globalRoundtrip_mm)) for c in result.candidates]
    return finite_json(dict(leading_index=int(result.leadingIndex), long_tracks=int(result.longTracks),
        pz0_GeV=float(result.leadingPz_GeV), missing_leading_links=int(result.missingLeadingLinks),
        stations=stations, anchors=anchors, candidates=candidates))


def summarize(v, case, identity):
    maximum = 0.
    for row in v['candidates']:
        independent = (row['cluster_loc1_mm']-row['state_loc1_mm'])**2/(row['cluster_variance_mm2']+row['state_variance_mm2'])
        maximum = max(maximum, abs(independent-row['r2']))
        assert math.isfinite(independent) and independent >= 0
        assert math.isclose(independent, row['r2'], rel_tol=2e-14, abs_tol=1e-12)
        assert row['global_roundtrip_mm'] < 1e-8
    features = []
    for station, counts in enumerate(v['stations']):
        values = np.array([row['r2'] for row in v['candidates'] if row['station'] == station])
        assert len(values) == counts['eligibleCandidates']
        assert counts['clusters'] == counts['leadingOwned']+counts['nonleading']
        assert counts['nonleading'] == counts['offMeasuredWafer']+counts['onMeasuredWafer']
        assert counts['onMeasuredWafer'] == sum(counts[k] for k in ['eligibleCandidates', 'candidateSurfaceMismatch',
            'candidateInvalidVariance', 'unusableAnchorCandidates', 'candidateMissingElement', 'candidateInvalidRDO'])
        available = identity and counts['eligibleWafers'] > 0
        features.append(dict(station=station, **counts, available=available,
            candidate_N=counts['eligibleCandidates'] if available else None,
            mean_exp_minus_half_r2=float(np.mean(np.exp(-values/2))) if available and len(values) else None,
            mean_log1p_r2=float(np.mean(np.log1p(values))) if available and len(values) else None,
            max_log1p_r2=float(np.max(np.log1p(values))) if available and len(values) else None,
            eligible_surface_fraction=counts['eligibleWafers']/counts['measuredWafers'] if identity and counts['measuredWafers'] else None,
            candidate_coverage_fraction=counts['eligibleCandidates']/counts['nonleading'] if identity and counts['nonleading'] else None,
            partial=counts['eligibleCandidates'] < counts['nonleading']))
    return dict(row=case['row'], entry=case['entry'], run=case['run'], event=case['event'], role=1,
        pz0_GeV=v['pz0_GeV'] if identity else None, leading_identity_known=identity, long_tracks=v['long_tracks'],
        missing_leading_links=v['missing_leading_links'], stations=features,
        anchor_counts=dict(total=len(v['anchors']), linked=sum(a['linked'] for a in v['anchors']),
            identifier_equal=sum(a['identifier_equal'] for a in v['anchors']),
            measurement=sum(a['measurement'] for a in v['anchors']), outlier=sum(a['outlier'] for a in v['anchors']),
            oneD_locX=sum(a['dimension'] == 1 and a['parameter_key'] == 1 for a in v['anchors']),
            same_surface=sum(a['same_surface'] for a in v['anchors']), valid=sum(a['valid'] for a in v['anchors'])),
        anchor_invalid_reasons=dict(missing_link=sum(not a['linked'] for a in v['anchors']),
            wrong_dimension=sum(a['dimension'] != 1 or a['parameter_key'] != 1 for a in v['anchors']),
            surface_mismatch=sum(not a['same_surface'] for a in v['anchors']),
            missing_or_nonfinite_covariance=sum(len(a['covariance']) != 25 or None in a['covariance'] for a in v['anchors']),
            nonpositive_or_missing_state_variance=sum(a['state_variance_mm2'] is None or a['state_variance_mm2'] <= 0 for a in v['anchors'])),
        anchor_surface_types=sorted(set((a['measurement_type'], a['state_type'], a['parameter_type']) for a in v['anchors'])),
        max_anchor_transform_difference=max((a['surface_max_element_difference'] for a in v['anchors'] if a['surface_max_element_difference'] is not None), default=None),
        max_state_roundtrip_mm=max((a['global_roundtrip_mm'] for a in v['anchors'] if a['same_surface'] and a['global_roundtrip_mm'] is not None), default=None),
        max_candidate_roundtrip_mm=max((a['global_roundtrip_mm'] for a in v['candidates']), default=None),
        independent_scaled_separation_max_delta=maximum)


class Capture(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        ROOT.gInterpreter.AddIncludePath(str(Path('ml').resolve()))
        assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n'+Path('ml/stage153_native.hxx').read_text())
        return PyAthena.StatusCode.Success

    def execute(self):
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
        v = snapshot(ROOT.Stage153.summarize(clusters, tracks, helper))
        assert v['long_tracks'] == old.longTracks
        assert [s['clusters'] for s in v['stations']] == list(old.clusters)
        assert v['pz0_GeV'] == finite_json(float(old.leadingPz))
        identity = v['pz0_GeV'] is not None and math.isclose(v['pz0_GeV'], case['pz'], rel_tol=3e-7, abs_tol=3e-5)
        phys_pz = max(list(phys_tree.Track_pz0), default=float('nan'))/1000
        assert math.isclose(phys_pz, case['pz'], rel_tol=3e-7, abs_tol=3e-5)
        record = summarize(v, case, identity)
        if not records:
            repeated = snapshot(ROOT.Stage153.summarize(clusters, tracks, helper))
            assert repeated == v
            record['same_process_native_repeat_exact'] = True
        if len(qa) < 4:
            qa.append(dict(row=case['row'], entry=case['entry'], run=case['run'], event=case['event'],
                anchors=v['anchors'][:4], candidates=v['candidates'][:8]))
        record['old_counts_exact'] = True
        record['execute_end_CPU_s'] = time.process_time()-cpu
        records.append(record)
        print('PARENT', len(records), case['entry'], 'anchors', record['anchor_counts'],
              'candidates', len(v['candidates']), flush=True)
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
acc.addEventAlgo(Capture('Stage153NativeSpatialSeparation'))
assert acc.run(maxEvents=len(cases)).isSuccess()
assert len(records) == len(cases)
phys_file.Close()
with gzip.open(CACHE/'native.json.gz', 'wt') as stream:
    json.dump(dict(records=records, QA=qa), stream, separators=(',', ':'), allow_nan=False)
summary = dict(passed=True, N=len(records), selected_input_role=1, request_index=0,
    REC=source['rec'], PHYS=phys_path, original_PHYS_branches=branches,
    geometry='FASERNU-04', conditions='OFLCOND-FASER-06', configured_tracker_only=True,
    native_support=any(s['available'] and s['eligibleCandidates'] for r in records for s in r['stations']),
    leading_identity_known_N=sum(r['leading_identity_known'] for r in records),
    exact_old_count_N=sum(r['old_counts_exact'] for r in records),
    same_process_first_parent_repeat=records[0]['same_process_native_repeat_exact'],
    CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
    ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()), RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    event_bytes=(CACHE/'native.json.gz').stat().st_size,
    calibrated_association_probability=False, calibrated_pull=False, new_G4=0, fits=0,
    reserved_forward=0, overall_complete=False)
assert summary['event_bytes'] <= plan['resources']['final_event_bytes_cap']
(OUT/'native_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print('SUMMARY', summary, flush=True)
