"""Read stored data tracks/PRDs and actual event-IOV mapping, no reconstruction."""
import gzip
import json
import math
import resource
import sys
import time
from pathlib import Path
import ROOT
from AthenaPython import PyAthena
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from FaserGeoModel.FaserGeoModelConfig import FaserGeometryCfg
from WaveformConditionsTools.WaveformCableMappingConfig import WaveformCableMappingCfg

OUT=Path('workbook/stage162_energy_ml');CACHE=Path('ntuples/energy_ml_stage162')
phase=sys.argv[1];assert phase in ['pilot','full','repeat']
manifest=json.loads((OUT/'matched_manifest.json').read_text())
assert manifest['metadata']['/TagInfo']['GeoFaser']=='FASERNU-04'
assert manifest['metadata']['/TagInfo']['IOVDbGlobalTag']=='OFLCOND-FASER-05'
count=64 if phase=='full' else 4
parents=manifest['records'][:count];assert all(r['unique_pair'] for r in parents)
cases=sorted(parents,key=lambda r:r['native_entry']);assert len({r['native_entry'] for r in cases})==count
cpu,tick=time.process_time(),time.perf_counter();records=[];starts=[];execute=[]

def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):return None
    return value

class Capture(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        ROOT.gInterpreter.AddIncludePath(str(Path('ml').resolve()))
        assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n'+Path('ml/stage162_native.hxx').read_text())
        return PyAthena.StatusCode.Success

    def execute(self):
        start=time.process_time();starts.append(start)
        store,det=PyAthena.py_svc('StoreGateSvc'),PyAthena.py_svc('DetectorStore')
        info=store.retrieve('xAOD::EventInfo','EventInfo');parent=cases[len(records)]
        assert (int(info.runNumber()),int(info.eventNumber()),int(info.timeStamp()))==(
            parent['run'],parent['event'],parent['native_timestamp'])
        clusters=store.retrieve('Tracker::FaserSCT_ClusterContainer','SCT_ClusterContainer')
        helper=det.retrieve('FaserSCT_ID','FaserSCT_ID')
        collections={}
        for key in ['CKFTrackCollectionWithoutIFT','CKFTrackCollectionBackwardWithoutIFT']:
            if not store.contains('TrackCollection',key):collections[key]=None;continue
            tracks=store.retrieve('TrackCollection',key);states=[]
            for s in ROOT.Stage149.states(tracks,helper,clusters):
                states.append(dict(long_index=int(s.longIndex),collection_index=int(s.collectionIndex),layers=int(s.layers),
                    state=list(s.values),parameters=list(s.parameters),covariance=list(s.covariance),
                    transform=list(s.transform),parameter_type=str(s.parameterType),surface_type=str(s.surfaceType),
                    prds=list(s.prds),measurements=[list(row) for row in s.measurements]))
            collections[key]=states
        records.append(clean(dict(PHYS_entry=parent['PHYS_entry'],native_entry=parent['native_entry'],
            run=int(info.runNumber()),event=int(info.eventNumber()),timestamp=int(info.timeStamp()),
            collections=collections,cluster_N=sum(len(c) for c in clusters),
            dictionary=[str(v) for v in ROOT.Stage162.dictionary(det.retrieve('IdDictManager','IdDict'))],
            cable_mapping=[[str(v) for v in row] for row in ROOT.Stage161.mapping(det.retrieve('VetoID','VetoID'))])))
        execute.append(time.process_time()-start)
        print('DATA_NATIVE',len(records),records[-1]['event'],flush=True)
        return PyAthena.StatusCode.Success

flags=initConfigFlags();flags.Input.Files=[manifest['REC']];flags.Input.isMC=False
flags.Input.ProjectName='data21';flags.IOVDb.DatabaseInstance='CONDBR3'
flags.GeoModel.FaserVersion='FASERNU-04';flags.IOVDb.GlobalTag='OFLCOND-FASER-05'
flags.Common.isOnline=False;flags.Beam.NumberOfCollisions=0.;flags.Detector.GeometryFaserSCT=True
flags.Concurrency.NumThreads=0;flags.Exec.MaxEvents=count;flags.Exec.OutputLevel=4;flags.lock()
acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.merge(FaserGeometryCfg(flags));acc.merge(WaveformCableMappingCfg(flags))
acc.getService('DBReplicaSvc').COOLSQLiteVetoPattern=''
left=0;excluded=[]
for case in cases:
    entry=case['native_entry']
    if left<entry:excluded.append(f'{left+1}-{entry}')
    left=entry+1
if left<manifest['native_N']:excluded.append(f"{left+1}-{manifest['native_N']}")
acc.getService('EventSelector').SkipEventRanges=','.join(excluded)
acc.addEventAlgo(Capture('Stage161StoredData'))
assert acc.run(maxEvents=count).isSuccess() and len(records)==count
records.sort(key=lambda r:r['PHYS_entry'])
with gzip.open(CACHE/f'{phase}_native.json.gz','wt') as stream:json.dump(records,stream,separators=(',',':'),allow_nan=False)
intervals=[starts[j]-starts[j-1] for j in range(2,len(starts))]
summary=dict(passed=True,N=count,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
    ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    first_execute_CPU_s=execute[0],execute_CPU_s=sum(execute),steady_complete_interval_CPU_s=sum(intervals),
    steady_complete_interval_max_CPU_s=max(intervals),steady_complete_interval_N=len(intervals),
    configured_conditions=dict(geometry=str(flags.GeoModel.FaserVersion),conditions=str(flags.IOVDb.GlobalTag),database=str(flags.IOVDb.DatabaseInstance)),
    scope='Two actual stored track collections, no merging/refit/digitization/ntuple writing; native waveform converter not invoked')
(OUT/f'{phase}_native_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary,flush=True)
