"""Bounded REC read with unused IFT surfaces and all native candidates; batch only."""
import gzip
import ctypes
import json
import math
import resource
import sys
import time
from pathlib import Path

import ROOT
from AthenaPython import PyAthena
from AthenaConfiguration.ComponentFactory import CompFactory
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from FaserActsKalmanFilter.MergeTracksConfig import MergeTrackCfg
from FaserActsGeometry.ActsGeometryConfig import ActsTrackingGeometryToolCfg
from MagFieldServices.MagFieldServicesConfig import MagneticFieldSvcCfg

ROOTDIR = Path.cwd()
OUT = ROOTDIR / 'workbook/stage190_energy_ml'
CACHE = ROOTDIR / 'ntuples/energy_ml_stage190'
phase = sys.argv[1]
P = json.loads((OUT / 'protocol.json').read_text())
tick, cpu = time.perf_counter(), time.process_time()
paths, cases, meta, references = [], [], [], {}
offset = 0
for source in P['sources']:
    count = P['pilot_per_source'] if phase == 'pilot' else len(source['cases'])
    selected = source['cases'][:count]
    f = ROOT.TFile.Open(source['rec'])
    assert f and not f.IsZombie()
    N = int(f.Get('CollectionTree').GetEntries())
    f.Close()
    paths.append(source['rec'])
    meta.append(dict(label=source['label'], N=N, requested_N=len(selected), bytes=Path(source['rec']).stat().st_size))
    with_phys = ROOT.TFile.Open(source['phys'])
    assert with_phys and not with_phys.IsZombie()
    t = with_phys.Get('nt')
    t.SetBranchStatus('*', 0)
    for b in ['run', 'eventID', 'Track_pz0']:
        t.SetBranchStatus(b, 1)
    for c in selected:
        assert t.GetEntry(c['PHYS_entry']) > 0
        pzs = list(t.Track_pz0)
        ref = dict(run=int(t.run), event=int(t.eventID), pz0_GeV=max(pzs)/1000 if pzs else None)
        assert (ref['run'],ref['event']) == (c['run'],c['event'])
        case = dict(c, label=source['label'], source_index=source['index'], global_entry=offset+c['entry'], reference=ref)
        if source['index'] >= 0:
            assert (ref['run'], ref['event']) == (c['run'], c['event'])
            assert ref['pz0_GeV'] == c['pz']
        cases.append(case)
    with_phys.Close()
    offset += N
records = []


class Snapshot(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        for library in ['libTrkTrack', 'libTrackerRIO_OnTrack', 'libTrackerPrepRawData', 'libTrackerIdentifier', 'libTrackerSimData', 'libActsCore']:
            assert ROOT.gSystem.Load(library)>=0, library
        self.bridge = ctypes.CDLL(str(ROOTDIR / 'stage188_bridge.so'), mode=__import__('os').RTLD_LAZY)
        self.bridge.stage188_observe.argtypes = [ctypes.c_void_p]*4
        self.bridge.stage188_observe.restype = ctypes.c_char_p
        return PyAthena.StatusCode.Success

    def execute(self):
        start = time.process_time()
        store, det = PyAthena.py_svc('StoreGateSvc'), PyAthena.py_svc('DetectorStore')
        info = store.retrieve('xAOD::EventInfo', 'EventInfo')
        case = cases[len(records)]
        ref = case['reference']
        assert (int(info.runNumber()), int(info.eventNumber()), int(info.timeStamp())) == (ref['run'], ref['event'], case['native_timestamp'])
        tracks = store.retrieve('TrackCollection', P['native_collection'])
        clusters = store.retrieve('Tracker::FaserSCT_ClusterContainer', 'SCT_ClusterContainer')
        helper = det.retrieve('FaserSCT_ID', 'FaserSCT_ID')
        sdo = store.retrieve('TrackerSimDataCollection', 'SCT_SDO_Map') if store.contains('TrackerSimDataCollection', 'SCT_SDO_Map') else ROOT.nullptr
        measurement = json.loads(self.bridge.stage188_observe(
            ROOT.addressof(tracks), ROOT.addressof(clusters), ROOT.addressof(helper),
            ROOT.addressof(sdo) if sdo else None))
        leading = measurement['leading']
        # Original float32 PHYS interface, not an adjustable matching tolerance.
        import struct
        f32 = lambda v: struct.unpack('f', struct.pack('f', v))[0]
        matched = bool(leading and ref['pz0_GeV'] is not None and f32(leading['pz0_GeV']*1000) == f32(ref['pz0_GeV']*1000))
        records.append(dict(case=case, measurement=measurement, original_leading_match=matched,
                            execute_CPU_s=time.process_time()-start, end_CPU_s=time.process_time()-cpu))
        print('IFT', case['label'], case['entry'], matched, measurement['reason'], len(measurement['wafers']), flush=True)
        return PyAthena.StatusCode.Success

    def finalize(self):
        assert len(records) == len(cases)
        with gzip.open(CACHE / f'{phase}_native.json.gz', 'wt') as f:
            json.dump(dict(records=records, metadata=meta), f, separators=(',', ':'), allow_nan=False)
        summary = dict(phase=phase, N=len(records), CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
            material_map=str(flags.TrackingGeometry.MaterialSource), bridge='gcc13 C++20 compiled native bridge',
            ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()), RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            matched_N=sum(r['original_leading_match'] for r in records),
            supported_N=sum(r['measurement']['start_supported'] for r in records),
            control_pz50_100_N=sum(r['original_leading_match'] and r['measurement']['leading'] is not None and 50<=r['measurement']['leading']['pz0_GeV']<100 for r in records),
            source_end_CPU_s={s['label']:[r['end_CPU_s'] for r in records if r['case']['label']==s['label']] for s in P['sources']})
        (OUT / f'{phase}_native_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        return PyAthena.StatusCode.Success


flags = initConfigFlags()
flags.Input.Files = paths
flags.Input.isMC = False
flags.IOVDb.DatabaseInstance = 'CONDBR3'
flags.Input.ProjectName = 'data21'
flags.GeoModel.FaserVersion = P['transport']['geometry']
flags.IOVDb.GlobalTag = P['transport']['conditions']
flags.TrackingGeometry.MaterialSource = '/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/acts/material-maps-alma9.json'
flags.Detector.GeometryFaserSCT = True
flags.Common.isOnline = False
flags.Beam.NumberOfCollisions = 0.
flags.Concurrency.NumThreads = 0
flags.Exec.MaxEvents = len(cases)
flags.Exec.OutputLevel = 4
flags.lock()
a = MainServicesCfg(flags)
a.merge(PoolReadCfg(flags))
from FaserGeoModel.FaserGeoModelConfig import FaserGeometryCfg
a.merge(FaserGeometryCfg(flags))
a.merge(MagneticFieldSvcCfg(flags))
gacc, geometry = ActsTrackingGeometryToolCfg(flags)
a.merge(gacc)
for name, material in [('Stage188Transport', True), ('Stage188NoMaterial', False)]:
    tool = CompFactory.FaserActsExtrapolationTool(name, TrackingGeometryTool=geometry, FieldMode='FASER',
        InteractionMultiScatering=material, InteractionEloss=material, InteractionRecord=True, MaxSteps=4000)
    a.addPublicTool(tool)
a.getService('DBReplicaSvc').COOLSQLiteVetoPattern = ''
left, excluded = 0, []
for c in cases:
    entry = c['global_entry']
    if left < entry:
        excluded.append(f'{left+1}-{entry}')
    left = entry+1
if left < offset:
    excluded.append(f'{left+1}-{offset}')
a.getService('EventSelector').SkipEventRanges = ','.join(excluded)
a.addEventAlgo(Snapshot('Stage188UnusedIFT'))
assert a.run(len(cases)).isSuccess()
assert len(records) == len(cases)
