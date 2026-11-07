"""Observe the exact merged collection in the official current ntuple job."""
import gzip
import json
import os
import resource
import shutil
import sys
import time
from pathlib import Path

import ROOT
from AthenaPython import PyAthena
from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator

rec, count, target, ntuple = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
header = Path(__file__).with_suffix('.hxx').resolve()
tick, cpu = time.perf_counter(), time.process_time()
records = []
original = ComponentAccumulator.run
cable_mapping = []
conditions = os.environ.get('NU_MU_CONTROL_CONDITIONS', 'OFLCOND-FASER-06')
assert conditions in ['OFLCOND-FASER-04', 'OFLCOND-FASER-06']
official_scope = {'__name__': '__main__'}
configured = {}


class Snapshot(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        ROOT.gInterpreter.AddIncludePath(str(header.parent))
        assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n'+header.read_text())
        return PyAthena.StatusCode.Success

    def execute(self):
        store, det = PyAthena.py_svc('StoreGateSvc'), PyAthena.py_svc('DetectorStore')
        info = store.retrieve('xAOD::EventInfo', 'EventInfo')
        clusters = store.retrieve('Tracker::FaserSCT_ClusterContainer', 'SCT_ClusterContainer')
        points = store.retrieve('FaserSCT_SpacePointContainer', 'SCT_SpacePointContainer')
        tracks = store.retrieve('TrackCollection', 'CKFTrackCollectionMergeWithoutIFT')
        raw = store.retrieve('FaserSCT_RDO_Container', 'SCT_RDOs')
        helper = det.retrieve('FaserSCT_ID', 'FaserSCT_ID')
        summary = ROOT.Stage124.summarize(clusters, points, tracks, raw, helper)
        states = ROOT.Stage149.states(tracks, helper, clusters)
        if not cable_mapping:
            cable_mapping.extend([[str(value) for value in row]
                                  for row in ROOT.Stage149.mapping(det.retrieve('VetoID', 'VetoID'))])
        native = []
        for s in states:
            native.append(dict(long_index=int(s.longIndex), collection_index=int(s.collectionIndex),
                layers=int(s.layers), state=list(s.values), parameters=list(s.parameters),
                covariance=list(s.covariance), transform=list(s.transform),
                parameter_type=str(s.parameterType), surface_type=str(s.surfaceType),
                prds=list(s.prds), measurements=[list(row) for row in s.measurements]))
        waves = []
        for detector in ['Calo', 'VetoNu', 'Veto', 'Trigger', 'Preshower']:
            key = detector+'WaveformHits'
            if not store.contains('xAOD::WaveformHitContainer', key):
                continue
            for hit in store.retrieve('xAOD::WaveformHitContainer', key):
                if hit.secondary():
                    continue
                waves.append(dict(detector=detector, channel=int(hit.channel()), status=int(hit.hit_status()),
                    raw_charge=float(hit.raw_integral()/50), raw_peak=float(hit.raw_peak()),
                    baseline=float(hit.baseline_mean()), baseline_rms=float(hit.baseline_rms()),
                    localtime=float(hit.localtime()) if int(hit.hit_status()) == 0 else None))
        records.append(dict(entry=len(records), run=int(info.runNumber()), event=int(info.eventNumber()),
            tracks=native, longTracks=int(summary.longTracks), waves=waves,
            clusters=list(summary.clusters), sp=int(summary.sp), spLinks=int(summary.spLinks),
            spMissing=int(summary.spMissing), measurements=int(summary.measurements),
            measurementMissing=int(summary.measurementMissing), rawMissing=int(summary.rawMissing),
            invalidStrip=int(summary.invalidStrip), duplicateClusterIdentifiers=int(summary.duplicateClusterIdentifiers),
            ownership_by_station=[list(summary.z)[24*j+17:24*j+21] for j in range(4)],
            execute_end_CPU_s=time.process_time()-cpu))
        print('NATIVE', len(records), 'tracks', len(native), 'waves', len(waves), flush=True)
        return PyAthena.StatusCode.Success

    def finalize(self):
        payload = json.dumps(dict(records=records, cable_mapping=cable_mapping,
                basis=['loc1_mm', 'loc2_mm', 'phi_rad', 'theta_rad', 'qOverP_MeV^-1'],
                covariance_units='outer product of basis units; stored unmodified',
                measurement_columns=['station', 'layer', 'side', 'PRD_pointer_in_container', 'owning_tracks',
                    'measurement_flag', 'outlier_flag', 'state_covariance_present', 'measurement_loc1_mm',
                    'state_loc1_mm', 'measurement_variance_mm2', 'state_variance_mm2'],
                state_columns=['x_mm', 'y_mm', 'z_mm', 'px_MeV', 'py_MeV', 'pz0_MeV', 'charge', 'chi2', 'ndof'],
                CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
                ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),
                RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                configured_conditions=configured), separators=(',', ':'))
        with gzip.open(target, 'wt') as stream:
            stream.write(payload)
        assert len(records) == count
        return PyAthena.StatusCode.Success


def run(acc, *args, **kwargs):
    flags = official_scope['configFlags']
    configured.update(conditions=str(flags.IOVDb.GlobalTag), geometry=str(flags.GeoModel.FaserVersion))
    assert configured['conditions'] == conditions and configured['geometry'] == 'FASERNU-04'
    acc.addEventAlgo(Snapshot('Stage149NativeState'))
    return original(acc, *args, **kwargs)


ComponentAccumulator.run = run
source = Path(shutil.which('faser_ntuple_maker.py')).read_text()
if conditions != 'OFLCOND-FASER-06':
    assert source.count('configFlags.lock()') == 1
    source = source.replace('configFlags.lock()', f'configFlags.IOVDb.GlobalTag = {conditions!r}\nconfigFlags.lock()')
sys.argv = ['faser_ntuple_maker.py', '--isMC', '--geom', 'TI12MC04', '--CKFTrackType', 'merge',
            '--nevents', str(count), '--outfile', ntuple, rec]
exec(compile(source, 'stage149-official-ntuple.py', 'exec'), official_scope)
