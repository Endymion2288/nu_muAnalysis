"""Actual fit-cluster particle pointers on the frozen original leading tracks."""
import ctypes
import gzip
import json
import resource
import sys
import time
from pathlib import Path

import ROOT
from AthenaPython import PyAthena
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from FaserActsKalmanFilter.MergeTracksConfig import MergeTrackCfg

ROOTDIR=Path.cwd();OUT=ROOTDIR/'workbook/stage194_energy_ml';CACHE=ROOTDIR/'ntuples/energy_ml_stage194'
P=json.loads((OUT/'protocol.json').read_text());phase=sys.argv[1]
with gzip.open(ROOTDIR/P['original_predictions'],'rt') as f:
    old={(r['case']['source_index'],r['case']['entry']):r for r in json.load(f)['records']}
paths=[];cases=[];offset=0;cpu=time.process_time();tick=time.perf_counter()
for source in P['sources']:
    selected=source['cases'][:P['pilot_per_source']] if phase=='pilot' else source['cases']
    f=ROOT.TFile.Open(source['rec']);assert f and not f.IsZombie()
    n=int(f.Get('CollectionTree').GetEntries());f.Close();paths.append(source['rec'])
    for c in selected:
        reference=old[(source['index'],c['entry'])]
        cases.append(dict(source_index=source['index'],label=source['label'],entry=c['entry'],global_entry=offset+c['entry'],
            run=reference['case']['reference']['run'],event=reference['case']['reference']['event']))
    offset+=n
records=[]


class Capture(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        for lib in ['libGeneratorObjects','libTrackerSimData','libTrkTrack','libTrackerRIO_OnTrack','libTrackerPrepRawData']:
            assert ROOT.gSystem.Load(lib)>=0
        self.bridge=ctypes.CDLL(str(ROOTDIR/'stage194_links.so'),mode=__import__('os').RTLD_LAZY)
        self.bridge.stage192_links.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_char_p]
        self.bridge.stage192_links.restype=ctypes.c_char_p
        self.bridge.stage194_fit.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p]
        self.bridge.stage194_fit.restype=ctypes.c_char_p
        return PyAthena.StatusCode.Success

    def execute(self):
        start=time.process_time();case=cases[len(records)]
        store=PyAthena.py_svc('StoreGateSvc');info=store.retrieve('xAOD::EventInfo','EventInfo')
        assert (int(info.runNumber()),int(info.eventNumber()))==(case['run'],case['event'])
        previous=old[(case['source_index'],case['entry'])]
        tracks=store.retrieve('TrackCollection',P['native_collection'])
        leading=previous['measurement']['leading']
        index=leading['collection_index'] if leading else -1
        truth=store.retrieve('McEventCollection','TruthEvent') if store.contains('McEventCollection','TruthEvent') else None
        sdo=store.retrieve('TrackerSimDataCollection','SCT_SDO_Map') if store.contains('TrackerSimDataCollection','SCT_SDO_Map') else None
        fit=json.loads(self.bridge.stage194_fit(ROOT.addressof(tracks),index,ROOT.addressof(sdo) if sdo else None))
        if leading:
            assert fit['leading']=={k:leading[k] for k in ['collection_index','pz0_GeV','charge']}
            assert fit['barcode_cluster_counts']==leading['barcode_cluster_counts']
        else:assert fit['leading'] is None
        strips=sorted({s for c in fit['clusters'] for s in c['strips']})
        result=json.loads(self.bridge.stage192_links(ROOT.addressof(sdo) if sdo else None,
            ROOT.addressof(truth) if truth else None,json.dumps(strips).encode()))
        records.append(dict(case=case,links=result,fit=fit,execute_CPU_s=time.process_time()-start,end_CPU_s=time.process_time()-cpu))
        if len(records)<=4 or len(records)%16==0:print('LINKS',phase,len(records),'/',len(cases),len(result['primary_muons']),flush=True)
        return PyAthena.StatusCode.Success

    def finalize(self):
        assert len(records)==len(cases)
        with gzip.open(CACHE/f'{phase}_native.json.gz','wt') as f:json.dump(dict(records=records),f,separators=(',',':'),allow_nan=False)
        summary=dict(passed=True,phase=phase,N=len(records),CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
            ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            slowest_postfirst_execute_CPU_s=max(r['execute_CPU_s'] for r in records[1:]))
        (OUT/f'{phase}_native_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        return PyAthena.StatusCode.Success


flags=initConfigFlags();flags.Input.Files=paths;flags.Input.isMC=True
flags.IOVDb.DatabaseInstance='OFLP200';flags.Input.ProjectName='data21'
flags.GeoModel.FaserVersion='FASERNU-04';flags.IOVDb.GlobalTag='OFLCOND-FASER-06'
flags.Concurrency.NumThreads=0;flags.Exec.MaxEvents=len(cases);flags.Exec.OutputLevel=4;flags.lock()
a=MainServicesCfg(flags);a.merge(PoolReadCfg(flags));a.merge(MergeTrackCfg(flags))
left=0;excluded=[]
for case in cases:
    if left<case['global_entry']:excluded.append(f"{left+1}-{case['global_entry']}")
    left=case['global_entry']+1
if left<offset:excluded.append(f'{left+1}-{offset}')
a.getService('EventSelector').SkipEventRanges=','.join(excluded)
a.addEventAlgo(Capture('Stage192TruthLinks'))
assert a.run(len(cases)).isSuccess()
