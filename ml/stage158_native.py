"""Frozen multi-REC native geometry observer; all scientific reads run in Condor."""
import gzip
import json
import math
import resource
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import ROOT
from AthenaPython import PyAthena
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from FaserActsKalmanFilter.MergeTracksConfig import MergeTrackCfg
from stage155_schema import inspect as inspect_schema
from stage156_geometry import snapshot, summarize, finite_json
from audited_features import configuration

OUT=Path('workbook/stage158_energy_ml');CACHE=Path('ntuples/energy_ml_stage158')
phase=sys.argv[1]
plan=json.loads((OUT/'protocol.json').read_text())
contract=json.loads(Path(plan['input_native_request']).read_text())
if phase=='pilot':
    indices=plan['pilot']['request_indices']+[125]
elif phase=='repeat':indices=[0]
else:indices=contract['batches'][int(phase.removeprefix('native_'))]
with np.load(plan['input_dataset']) as source:
    original={key:source[key] for key in ['x','role','run','eventID','pz']}
names=configuration()['features']
assert original['x'].shape==(89033,62)
tick,cpu=time.perf_counter(),time.process_time()
paths=[];cases=[];metadata=[];offset=0
for index in indices:
    source=contract['requests'][index]
    selected=sorted((r for r in source['cases'] if r['role']>0),key=lambda r:r['entry'])
    if phase=='pilot':
        selected=([r for r in selected if r['row']==40738] if index==125 else
                  [r for r in selected if r['role']==1][:40])
    elif phase=='repeat':selected=[r for r in selected if r['role']==1][:4]
    if not selected:continue
    schema=inspect_schema(source['rec'])
    assert schema['verified'],schema
    file=ROOT.TFile.Open(source['rec']);assert file and not file.IsZombie()
    total=int(file.Get('CollectionTree').GetEntries());file.Close()
    assert max(r['entry'] for r in selected)<total
    if source['origin']==55:assert total==source['parent_N']
    metadata.append(dict(request_index=index,origin=source['origin'],component=source['component'],
        REC=source['rec'],parent_N=total,requested_N=len(selected),schema=schema))
    paths.append(source['rec'])
    cases.extend(dict(r,source_index=index,global_entry=offset+r['entry']) for r in selected)
    offset+=total
assert cases and len({r['row'] for r in cases})==len(cases)
assert all(a['global_entry']<b['global_entry'] for a,b in zip(cases,cases[1:]))
records=[];QA=[];event_times=defaultdict(list);anchor_failures=defaultdict(int)


class Capture(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        ROOT.gInterpreter.AddIncludePath(str(Path('ml').resolve()))
        assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n'+Path('ml/stage155_native.hxx').read_text())
        return PyAthena.StatusCode.Success

    def execute(self):
        start=time.process_time();case=cases[len(records)];row=case['row']
        assert original['role'][row]==case['role'] and case['role']>0
        store=PyAthena.py_svc('StoreGateSvc');det=PyAthena.py_svc('DetectorStore')
        info=store.retrieve('xAOD::EventInfo','EventInfo')
        assert (int(info.runNumber()),int(info.eventNumber()))==(case['run'],case['event'])
        assert (case['run'],case['event'])==(original['run'][row],original['eventID'][row])
        clusters=store.retrieve('Tracker::FaserSCT_ClusterContainer','SCT_ClusterContainer')
        points=store.retrieve('FaserSCT_SpacePointContainer','SCT_SpacePointContainer')
        tracks=store.retrieve('TrackCollection','CKFTrackCollectionMergeWithoutIFT')
        raw=store.retrieve('FaserSCT_RDO_Container','SCT_RDOs')
        helper=det.retrieve('FaserSCT_ID','FaserSCT_ID')
        old=ROOT.Stage124.summarize(clusters,points,tracks,raw,helper)
        v=snapshot(ROOT.Stage155.summarize(clusters,tracks,helper))
        assert v['long_tracks']==int(old.longTracks)
        assert [s['clusters'] for s in v['stations']]==list(old.clusters)
        assert v['pz0_GeV']==finite_json(float(old.leadingPz))
        count_closed=(list(old.clusters)==[int(original['x'][row,names.index(f'nClusters{s}')]) for s in range(4)]
            and int(old.sp)==int(original['x'][row,names.index('SpacePoints')])
            and int(old.longTracks)==int(original['x'][row,names.index('longTracks')]))
        identity=(v['pz0_GeV'] is not None and math.isclose(v['pz0_GeV'],case['pz'],rel_tol=3e-7,abs_tol=3e-5))
        assert math.isclose(case['pz'],float(original['pz'][row]),rel_tol=0,abs_tol=1e-12)
        geometry=summarize(v,case,bool(identity and count_closed))
        if not records:assert snapshot(ROOT.Stage155.summarize(clusters,tracks,helper))==v
        for anchor in v['anchors']:
            if anchor['valid']:continue
            for key in ['linked','identifier_equal','measurement','measurement_detector_same','exact_float32','plane_compatible']:
                if not anchor[key]:anchor_failures[key]+=1
            if anchor['outlier']:anchor_failures['outlier']+=1
        if len(QA)<4:
            QA.append(dict(row=row,entry=case['entry'],run=case['run'],event=case['event'],
                anchors=v['anchors'][:4],candidates=v['candidates'][:8]))
        elapsed=time.process_time()-start;event_times[case['source_index']].append(elapsed)
        records.append(dict(row=row,source_index=case['source_index'],role=case['role'],run=case['run'],event=case['event'],
            entry=case['entry'],geometry=geometry,count_closed=bool(count_closed),leading_match=bool(identity),
            native_pz0_GeV=v['pz0_GeV'],old_counts=dict(clusters=list(old.clusters),sp=int(old.sp),longTracks=int(old.longTracks)),
            execute_CPU_s=elapsed))
        if len(records)%100==0 or len(records)<=4:print('NATIVE',phase,len(records),'row',row,flush=True)
        return PyAthena.StatusCode.Success


flags=initConfigFlags();flags.Input.Files=paths;flags.Input.isMC=True
flags.IOVDb.DatabaseInstance='OFLP200';flags.Input.ProjectName='data21'
flags.GeoModel.FaserVersion='FASERNU-04';flags.IOVDb.GlobalTag='OFLCOND-FASER-06'
flags.Detector.GeometryFaserSCT=True;flags.Concurrency.NumThreads=0
flags.Exec.MaxEvents=len(cases);flags.Exec.OutputLevel=4;flags.lock()
acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.merge(MergeTrackCfg(flags))
left=0;excluded=[]
for case in cases:
    entry=case['global_entry']
    if left<entry:excluded.append(f'{left+1}-{entry}')
    left=entry+1
if left<offset:excluded.append(f'{left+1}-{offset}')
acc.getService('EventSelector').SkipEventRanges=','.join(excluded)
acc.addEventAlgo(Capture('Stage158ActualSpatialObserver'))
assert acc.run(maxEvents=len(cases)).isSuccess()
assert len(records)==len(cases)
with gzip.open(CACHE/f'{phase}.json.gz','wt') as stream:
    json.dump(dict(records=records,QA=QA),stream,separators=(',',':'),allow_nan=False)
report=dict(phase=phase,passed=True,N=len(records),metadata=metadata,
    count_closed_N=sum(r['count_closed'] for r in records),leading_match_N=sum(r['leading_match'] for r in records),
    valid_geometry_parent_N=sum(any(s['available'] for s in r['geometry']['stations']) for r in records),
    first_parent_native_repeat_exact=True,anchor_failure_flags=dict(anchor_failures),
    event_CPU_s={str(k):v for k,v in event_times.items()},CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
    ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    event_bytes=(CACHE/f'{phase}.json.gz').stat().st_size,new_G4=0,energy_fits=0,reserved_forward=0,
    calibrated_covariance=False,overall_complete=False)
(OUT/f'{phase}_summary.json').write_text(json.dumps(report,indent=2)+'\n')
print('SUMMARY',phase,{k:v for k,v in report.items() if k not in ['metadata','event_CPU_s']},flush=True)
