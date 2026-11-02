#!/usr/bin/env python
"""Same-event SCT-only digitization replay; original RDOs retained as reference."""
import argparse
import json
import math
import resource
import re
import time
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--input-rdo',required=True)
p.add_argument('--entries',required=True,help='JSON list of original merged RDO entries')
p.add_argument('--mode',choices=['nominal','nonoise'],required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--run',type=int,required=True)
p.add_argument('--with-tracking',action='store_true')
p.add_argument('--tracking-helper',type=Path)
p.add_argument('--expected-cases',type=Path)
p.add_argument('--original-hits',action='store_true',help='Load original SCT HITS; avoid the lossy re-persisted RDO copy')
p.add_argument('--converter-header',type=Path,default=Path(__file__).resolve().parents[2]/'calypso/Tracker/TrackerEventCnv/TrackerEventAthenaPool/src/FaserSCT3_RawDataCnv_p4.h')
a=p.parse_args()
entries=json.loads(Path(a.entries).read_text());assert entries==sorted(set(entries)) and entries
expected=json.loads(a.expected_cases.read_text()) if a.expected_cases else None
if expected:assert [c['entry'] for c in expected]==entries
start,cpu=time.perf_counter(),time.process_time()
from AthenaCommon.Configurable import Configurable
Configurable.configurableRun3Behavior=True
from AthenaConfiguration.ComponentFactory import CompFactory
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
flags=initConfigFlags()
flags.Input.isMC=True
flags.IOVDb.DatabaseInstance='OFLP200'
flags.IOVDb.GlobalTag='OFLCOND-FASER-05'
flags.Input.ProjectName='mc20'
flags.Input.Files=[a.input_rdo]
flags.GeoModel.FaserVersion='FASERNU-CALONU'
flags.TrackingGeometry.MaterialSource='/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/acts/material-maps-alma9.json'
flags.Beam.NumberOfCollisions=0.
flags.Digitization.EnableTruth=True
flags.Exec.SkipEvents=entries[0]
flags.Concurrency.NumThreads=0
flags.Concurrency.NumConcurrentEvents=1
flags.lock()
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from FaserSCT_Digitization.FaserSCT_DigitizationConfigNew import FaserSCT_DigitizationBasicCfg,FaserSCT_DigitizationToolCfg
acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags))
import AthenaPython.PyAthena as PyAthena
from AthenaPython.PyAthena import StatusCode
event_clock={}
class EventClock(PyAthena.Alg):
    def execute(self):
        event_clock.update(wall=time.perf_counter(),cpu=time.process_time())
        return StatusCode.Success
acc.addEventAlgo(EventClock(name='Stage53EventClock'))
if a.original_hits:
    class OriginalHitsLoader(PyAthena.Alg):
        def initialize(self):
            import ROOT
            import StoreGateBindings.Bindings
            self.root=ROOT;self.files={};self.ordinal=0
            ROOT.gSystem.Load('libTrackerSimEventTPCnv.so')
            assert ROOT.gInterpreter.Declare('''
#define HEPMC3 1
#include "TrackerSimEventTPCnv/TrackerHits/FaserSiHitCollectionCnv_p3a.h"
#include "GaudiKernel/MsgStream.h"
FaserSiHitCollection* Stage53OriginalHits(const FaserSiHitCollection_p3a* p) {
    MsgStream log(nullptr,"Stage53OriginalHits");
    FaserSiHitCollectionCnv_p3a converter;
    return converter.createTransient(p,log);
}
''')
            return StatusCode.Success
        def execute(self):
            entry=entries[self.ordinal];self.ordinal+=1
            match=re.search(r'-(\d{5})-(\d{5})-RDO.root$',a.input_rdo)
            assert match
            path=str(Path(a.input_rdo).parents[2]/'sim/s0015'/
                (Path(a.input_rdo[:match.start()]).name+f'-{int(match[1])+entry//10000:05}-HITS.root'))
            if path not in self.files:
                file=self.root.TFile.Open(path);assert file and not file.IsZombie()
                tree=file.Get('CollectionTree');tree.SetBranchStatus('*',0)
                tree.SetBranchStatus('FaserSiHitCollection_p3a_SCT_Hits',1)
                self.files[path]=(file,tree)
            file,tree=self.files[path];assert tree.GetEntry(entry%10000)>0
            hits=self.root.Stage53OriginalHits(tree.FaserSiHitCollection_p3a_SCT_Hits)
            self.root.SetOwnership(hits,False)
            assert self.evtStore.record(hits,'SCT_Hits_Original')
            return StatusCode.Success
    acc.addEventAlgo(OriginalHitsLoader(name='Stage53OriginalHitsLoader'))
if a.with_tracking:
    from FaserGeoModel.ScintGMConfig import ScintGeometryCfg
    from DipoleGeoModel.DipoleGeoModelConfig import DipoleGeometryCfg
    acc.merge(ScintGeometryCfg(flags))
    acc.merge(DipoleGeometryCfg(flags))
# Only SCT geometry is instantiated; no mismatched CaloNu ID helper is called.
tool=acc.popToolsAndMerge(FaserSCT_DigitizationToolCfg(flags,
    OutputObjectName='SCT_RDOs_Replay',OutputSDOName='SCT_SDO_Map_Replay'))
tool.SurfaceChargesGenerator.SubtractTime=-999.
if a.original_hits:tool.InputObjectName='SCT_Hits_Original'
if a.mode=='nonoise':tool.FrontEnd.NoiseOn=False
properties={k:str(getattr(tool.FrontEnd,k)) for k in ['NoiseOn','AnalogueNoiseOn','UseCalibData','Threshold','TimeOfThreshold','DataCompressionMode','DataReadOutMode'] if hasattr(tool.FrontEnd,k)}
print('STAGE53_FRONTEND',json.dumps(properties),flush=True)
acc.merge(FaserSCT_DigitizationBasicCfg(flags,PileUpTools=tool))
# EventSelectorAthenaPool uses one-based input positions, with inclusive ranges.
if entries!=list(range(entries[0],entries[-1]+1)):
    acc.getService('EventSelector').SkipEventRanges=','.join(
        f'{left+2}-{right}' for left,right in zip(entries,entries[1:]) if right>left+1)
    acc.getService('EventSelector').OutputLevel=4
from TrackerPrepRawDataFormation.TrackerPrepRawDataFormationConfig import FaserSCT_ClusterizationBasicCfg
from TrackerSpacePointFormation.TrackerSpacePointFormationConfig import TrackerSpacePointFinderCfg
from TrackerSegmentFit.TrackerSegmentFitConfig import SegmentFitAlgCfg
for label,key in [('Reference','SCT_RDOs'),('Replay','SCT_RDOs_Replay')]:
    acc.merge(FaserSCT_ClusterizationBasicCfg(flags,name='Clusterization'+label,
        DataObjectName=key,ClustersName='SCT_Clusters_'+label,
        ClustersLinkName_='SCT_Clusters_'+label,checkBadChannels=True))
    acc.merge(TrackerSpacePointFinderCfg(flags,name='SpacePointFinder'+label,
        SCT_ClustersName='SCT_Clusters_'+label,SpacePointsSCTName='SCT_SpacePoints_'+label,
        SpacePointsOverlapName='SCT_Overlap_'+label))
    acc.merge(SegmentFitAlgCfg(flags,name='SegmentFit'+label,ClustersName='SCT_Clusters_'+label,
        OutputCollection='Segments_'+label,ReducedChi2Cut=25.,SharedHitFraction=.61,
        MinClustersPerFit=5,TanThetaXZCut=.083))
    if a.with_tracking:
        from FaserActsKalmanFilter.GhostBustersConfig import GhostBustersCfg
        from FaserActsKalmanFilter.CKF2Config import CKF2Cfg
        acc.merge(GhostBustersCfg(flags,name='GhostBusters'+label,
            TrackCollection='Segments_'+label,OutputCollection='GhostSegments_'+label,MakeHist=False))
        ckfacc=CKF2Cfg(flags,name='CKF_'+label,actsOutputTag='stage53_'+label,
            maskedLayers=list(range(6)),OutputCollection='Tracks_'+label,
            BackwardPropagation=True,noDiagnostics=True)
        seed=ckfacc.getEventAlgo('CKF_'+label).TrackSeed
        seed.TrackCollection='GhostSegments_'+label
        seed.ClusterContainer='SCT_Clusters_'+label
        seed.SpacePoints='SCT_SpacePoints_'+label
        acc.merge(ckfacc)
if a.with_tracking:
    from FaserActsGeometry.ActsGeometryConfig import ActsExtrapolationToolCfg
    acc.merge(ActsExtrapolationToolCfg(flags,MaxSteps=10000))
import AthenaPython.PyAthena as PyAthena
from AthenaPython.PyAthena import StatusCode

class Snapshot(PyAthena.Alg):
    def __init__(self):
        super().__init__(name='TrackerNoiseSnapshot');self.records=[]
    def initialize(self):
        import StoreGateBindings.Bindings
        import ROOT
        ROOT.gSystem.Load('libTrackerEventAthenaPool.so')
        assert a.converter_header.is_file()
        # Compare identical persistent representations using the production converter.
        # p4 omits the redundant strip bits from the transient word; never mask
        # unexplained differences or loosen the exact identifier/word requirement.
        assert ROOT.gInterpreter.Declare('''
#include "'''+str(a.converter_header)+'''"
#include "TrackerIdentifier/FaserSCT_ID.h"
#include "GaudiKernel/MsgStream.h"
std::vector<unsigned long long> Stage53RoundTrip(const FaserSCT_RDORawData* h, const FaserSCT_ID* id) {
    auto typed=dynamic_cast<const FaserSCT3_RawData*>(h);
    if (!typed) throw std::runtime_error("Expected SCT3 raw data");
    FaserSCT3_RawDataCnv_p4 converter(id);
    converter.setWaferId(id->wafer_id(h->identify()));
    MsgStream log(nullptr,"Stage53RoundTrip");
    FaserSCT3_RawData_p4 persisted;
    converter.transToPers(typed,&persisted,log);
    FaserSCT3_RawData back;
    converter.persToTrans(&persisted,&back,log);
    return {back.identify().get_compact(),back.getWord()};
}
''')
        self.root=ROOT
        assert ROOT.gInterpreter.Declare('''
#include "AthenaKernel/IEvtSelectorSeek.h"
#include "GaudiKernel/ServiceHandle.h"
int Stage53InputEntry() {
    ServiceHandle<IEvtSelector> selector("EventSelector","Stage53InputEntry");
    if (selector.retrieve().isFailure()) throw std::runtime_error("Missing selector");
    IEvtSelector::Context* context=nullptr;
    if (selector->createContext(context).isFailure()) throw std::runtime_error("Missing input context");
    auto seek=dynamic_cast<IEvtSelectorSeek*>(selector.get());
    if (!seek) throw std::runtime_error("Missing selector seek interface");
    int entry=seek->curEvent(*context)-1;
    delete context;
    return entry;
}
''')
        if a.with_tracking:
            assert a.tracking_helper and a.tracking_helper.is_file()
            assert ROOT.gSystem.Load(str(a.tracking_helper.resolve()))>=0
            assert ROOT.gInterpreter.Declare('''
#include "TrkTrack/TrackCollection.h"
class FaserSCT_ID;
std::vector<std::vector<double>> Stage53Tracks(const TrackCollection*,const FaserSCT_ID*);
''')
        self.sct=self.detStore['FaserSCT_ID']
        return StatusCode.Success
    def execute(self):
        info=self.evtStore['EventInfo'];reference=[];replay=[];roundtrip={}
        for key,dest in [('SCT_RDOs',reference),('SCT_RDOs_Replay',replay)]:
            roundtrip[key]=[]
            for coll in self.evtStore[key]:
                for hit in coll:
                    dest.append((int(hit.identify().get_compact()),int(hit.getWord())))
                    roundtrip[key].append(tuple(int(x) for x in self.root.Stage53RoundTrip(hit,self.sct)))
            roundtrip[key].sort()
        reference.sort();replay.sort()
        counts={}
        for label in ['Reference','Replay']:
            count=[0]*4
            for coll in self.evtStore['SCT_Clusters_'+label]:
                count[int(self.sct.station(coll.identify()))]+=len(coll)
            counts[label]=count
        ref=set(reference);rep=set(replay)
        rec=dict(ordinal=len(self.records),run=int(info.runNumber()),event=int(info.eventNumber()),
                 entry=int(self.root.Stage53InputEntry()),
                 rdo_reference=len(reference),rdo_replay=len(replay),rdo_exact_equal=reference==replay,
                 only_reference_words=len(ref-rep),only_replay_words=len(rep-ref),clusters=counts,
                 identifiers_equal=[x[0] for x in reference]==[x[0] for x in replay],
                 word_values_equal=sorted(x[1] for x in reference)==sorted(x[1] for x in replay),
                 first_reference_words=reference[:3],first_replay_words=replay[:3])
        rec['rdo_p4_exact_equal']=reference==roundtrip['SCT_RDOs_Replay']
        rec['reference_p4_idempotent']=reference==roundtrip['SCT_RDOs']
        rec['spacepoints']={label:sum(len(c) for c in self.evtStore['SCT_SpacePoints_'+label]) for label in ['Reference','Replay']}
        rec['segments']={label:len(self.evtStore['Segments_'+label]) for label in ['Reference','Replay']}
        if a.with_tracking:
            rec['tracks']={label:[[float(x) for x in row] for row in self.root.Stage53Tracks(self.evtStore['Tracks_'+label],self.sct)] for label in ['Reference','Replay']}
            if expected:
                case=expected[len(self.records)]
                def selected(tracks):
                    if len(tracks)!=1:return False
                    p,pz,layers,ndof,chi2,q,x,y,tx,ty,xt,yt=max(tracks,key=lambda t:t[1])
                    return (layers>=7 and ndof>=9 and chi2/ndof<15 and 100000<=p<1000000
                            and abs(x)<500 and abs(y)<500 and math.hypot(tx,ty)<.025
                            and all(v>40 for v in case['veto_raw_pC'])
                            and abs(xt)<80 and abs(yt)<80 and abs(q)==1)
                rec['selected']={label:selected(tracks) for label,tracks in rec['tracks'].items()}
        rec['event_wall_s']=time.perf_counter()-event_clock['wall']
        rec['event_cpu_s']=time.process_time()-event_clock['cpu']
        self.records.append(rec);print('STAGE53_EVENT',json.dumps(rec),flush=True)
        return StatusCode.Success
    def finalize(self):
        assert len(self.records)==len(entries),(len(self.records),len(entries))
        assert all(r['run']==a.run for r in self.records)
        assert [r['entry'] for r in self.records]==entries
        if expected:
            for rec,case in zip(self.records,expected):
                assert rec['event']==case['event']
                rec['original_counts_equal']=(rec['clusters']['Reference']+[rec['spacepoints']['Reference'],rec['segments']['Reference']])==case['original_counts']
        self.nominal_gate=all(r['rdo_p4_exact_equal'] and r['reference_p4_idempotent']
            and r['clusters']['Reference']==r['clusters']['Replay']
            and r['spacepoints']['Reference']==r['spacepoints']['Replay']
            and r['segments']['Reference']==r['segments']['Replay']
            and r.get('original_counts_equal',True)
            and all(r.get('selected',{'pilot_unchecked':True}).values()) for r in self.records)
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(dict(mode=a.mode,input=a.input_rdo,requested_entries=entries,
            frontend=properties,original_hits_diagnostic=a.original_hits,
            material_source=flags.TrackingGeometry.MaterialSource,
            records=self.records,nominal_gate=self.nominal_gate,wall_s=time.perf_counter()-start,cpu_s=time.process_time()-cpu,
            root_files_read=[dict(name=f.GetName(),bytes_read=int(f.GetBytesRead())) for f in self.root.gROOT.GetListOfFiles()],
            root_all_files_bytes_read=int(self.root.TFile.GetFileBytesRead()),
            peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024),indent=2)+'\n')
        return StatusCode.Success

acc.addEventAlgo(Snapshot())
acc.getService('MessageSvc').Format='% F%40W%S%7W%R%T %0W%M'
sc=acc.run(maxEvents=len(entries))
raise SystemExit(not sc.isSuccess())
