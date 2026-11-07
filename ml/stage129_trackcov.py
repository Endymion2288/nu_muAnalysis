"""Actual early segment covariance pilot; nominal segment momentum is diagnostic only."""
import gzip,json,resource,sys,time
from pathlib import Path
import ROOT
from AthenaPython import PyAthena
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from FaserActsKalmanFilter.MergeTracksConfig import MergeTrackCfg
OUT=Path('workbook/stage129_energy_ml');index=int(sys.argv[1]);plan=json.loads((OUT/'extraction_contract.json').read_text());full=index>=1000
sources=[plan['requests'][j] for j in plan['batches'][index-1000]] if full else [plan['requests'][index]]
paths=[];cases=[];offset=0
for source in sources:
 f=ROOT.TFile.Open(source['rec']);assert f and not f.IsZombie();N=int(f.Get('CollectionTree').GetEntries());f.Close();paths.append(source['rec'])
 selected=source['cases'] if full else [c for c in source['cases'] if c['role']==1][:32]
 cases.extend([dict(c,global_entry=offset+c['entry']) for c in selected]);offset+=N
tick,cpu=time.perf_counter(),time.process_time();records=[];mapping=[]
class Snapshot(PyAthena.Alg):
 def initialize(self):
  import StoreGateBindings.Bindings
  assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n'+Path('ml/stage129_trackcov.hxx').read_text());return PyAthena.StatusCode.Success
 def execute(self):
  store=PyAthena.py_svc('StoreGateSvc');det=PyAthena.py_svc('DetectorStore');info=store.retrieve('xAOD::EventInfo','EventInfo');case=cases[len(records)];assert (int(info.runNumber()),int(info.eventNumber()))==(case['run'],case['event'])
  h=det.retrieve('FaserSCT_ID','FaserSCT_ID');group={}
  for key in (['Segments'] if full else ['SegmentFit','Segments','CKFTrackCollection','CKFTrackCollectionWithoutIFT','CKFTrackCollectionMergeWithoutIFT']):
   if not store.contains('TrackCollection',key):group[key]=dict(available=False);continue
   ts=store.retrieve('TrackCollection',key);v=ROOT.Stage129.tracks(ts,h)
   use=[j for j,x in enumerate(v.values) if not full or (x[8]==1 and x[11]>0 and x[9]>=5)]
   values=[list(v.values[j]) for j in use]
   if full:
    for value in values:value[5]=float('nan') # nominal100GeV never survives into deployment cache
   group[key]=dict(available=True,values=values,prds=[list(v.prds[j]) for j in use])
  records.append(dict(row=case['row'],entry=case['entry'],tracks=group));return PyAthena.StatusCode.Success
flags=initConfigFlags();flags.Input.Files=paths;flags.Input.isMC=True;flags.IOVDb.DatabaseInstance='OFLP200';flags.Input.ProjectName='data21';flags.GeoModel.FaserVersion='FASERNU-04';flags.IOVDb.GlobalTag='OFLCOND-FASER-06';flags.Detector.GeometryFaserSCT=True;flags.Concurrency.NumThreads=0;flags.Exec.MaxEvents=len(cases);flags.Exec.OutputLevel=4;flags.lock()
a=MainServicesCfg(flags);a.merge(PoolReadCfg(flags));a.merge(MergeTrackCfg(flags));excluded=[];left=0
for c in cases:
 if left<c['global_entry']:excluded.append(f'{left+1}-{c["global_entry"]}')
 left=c['global_entry']+1
a.getService('EventSelector').SkipEventRanges=','.join(excluded);a.addEventAlgo(Snapshot('Stage129TrackCovariance'));assert a.run(len(cases)).isSuccess()
report=dict(source=index,records=records,columns=['x_mm','y_mm','z_mm','tx','ty','nominal_pz_diagnostic_GeV','plane','cov_available','station_mask','PRD_N','chi2','ndof']+[f'C{i}{j}' for i in range(4) for j in range(4)],momentum_policy='nominal segment pz diagnostic only; never input or exact hadron momentum',CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
if full:
 with gzip.open(f'ntuples/energy_ml_stage129/trackcov_{index}.json.gz','wt') as f:json.dump(records,f,separators=(',',':'))
 report['events_with_2_IFT']=sum(len(r['tracks']['Segments'].get('values',[]))>=2 for r in records);report['N']=len(records);del report['records']
(OUT/f'trackcov_{index}.json').write_text(json.dumps(report,separators=(',',':'))+'\n');print('TRACK_COV',index,len(records),flush=True)
