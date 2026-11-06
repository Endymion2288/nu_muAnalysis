"""Pinned native reconstruction/REC observer for actual strip/PRD/SP/TSOS links."""
import gzip,json,math,sys,time,resource
from pathlib import Path
index=int(sys.argv[1]);phase=sys.argv[2];plan=json.loads(Path('workbook/stage124_energy_ml/native_contract.json').read_text());source=plan['requests'][index]
cases=source['cases']
if phase.startswith('pilot'):cases=[c for c in cases if c['role'] in [1,2]][:40]
if phase=='mismatch':cases=[c for c in cases if c['row']==40738]
sources=[source]
if phase in ['native','repair']:
 sources=[plan['requests'][j] for j in plan['batches'][index]]
 import ROOT
 cases=[];paths=[];offset=0;metadata=[]
 for ss in sources:
  f=ROOT.TFile.Open(ss['rec']);assert f and not f.IsZombie(),ss['rec'];n=int(f.Get('CollectionTree').GetEntries());f.Close()
  assert max(c['entry'] for c in ss['cases'])<n
  if ss['origin']==55:assert n==ss['parent_N'],(n,ss['parent_N'])
  metadata.append(dict(source_index=ss['index'],path=ss['rec'],parent_N=n));paths.append(ss['rec'])
  cases.extend([dict(c,source_index=ss['index'],global_entry=offset+c['entry']) for c in ss['cases']]);offset+=n
 source=dict(sources[0],parent_N=offset)
else:
 cases=[dict(c,source_index=source['index'],global_entry=c['entry']) for c in cases];paths=[source['rec']];metadata=[]
assert cases;entries=[c['global_entry'] for c in cases];records=[];tick=time.perf_counter();cpu=time.process_time()
from AthenaPython import PyAthena
class Snapshot(PyAthena.Alg):
 def initialize(self):
  import ROOT
  import StoreGateBindings.Bindings
  assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n')
  assert ROOT.gInterpreter.Declare(Path('ml/stage124_native.hxx').read_text())
  return PyAthena.StatusCode.Success
 def execute(self):
  import ROOT
  store=PyAthena.py_svc('StoreGateSvc');det=PyAthena.py_svc('DetectorStore');c=cases[len(records)]
  info=store.retrieve('xAOD::EventInfo','EventInfo');assert (int(info.runNumber()),int(info.eventNumber()))==(c['run'],c['event'])
  cluster=store.retrieve('Tracker::FaserSCT_ClusterContainer','SCT_ClusterContainer');sp=store.retrieve('FaserSCT_SpacePointContainer','SCT_SpacePointContainer');track=store.retrieve('TrackCollection','CKFTrackCollectionMergeWithoutIFT');raw=store.retrieve('FaserSCT_RDO_Container','SCT_RDOs');helper=det.retrieve('FaserSCT_ID','FaserSCT_ID')
  result=ROOT.Stage124.summarize(cluster,sp,track,raw,helper)
  matched=math.isclose(result.leadingPz,c['pz'],rel_tol=3e-7,abs_tol=3e-5)
  z=list(result.z)
  if not matched:
   # Frozen X uses the original PHYS leading track. Its REC identity is
   # unresolved here: retain parent and independent PRD/SP resources, but
   # never silently substitute a different leading track or loosen tolerance.
   for j in [24*st+k for st in range(4) for k in [17,18]]+[98,103]:z[j]=float('nan')
   print('LEADING_ID_UNKNOWN',c,result.leadingPz,flush=True)
  audit={}
  if phase=='mismatch':
   import csv
   manifest=list(csv.DictReader(open('ml/configs/low_energy_files.tsv'),delimiter='\t'));path=manifest[source['source_index']]['input']
   f=ROOT.TFile.Open(path);tree=f.Get('nt');assert tree.GetEntry(c['entry'])>0;assert int(tree.eventID)==c['event']
   for name in ['Track_pz0','Track_px0','Track_py0','Track_x0','Track_y0','Track_z0','Track_charge','Track_Chi2','Track_nDoF','Track_nLayers','longTracks']:
    if tree.GetBranch(name):
     v=getattr(tree,name);audit[name]=list(v) if hasattr(v,'size') else float(v)
   audit['input']=path;f.Close()

  records.append(dict(row=c['row'],source_index=c['source_index'],entry=c['entry'],event=c['event'],run=c['run'],pz_GeV=result.leadingPz,z=z,pz_match=matched,track_audit=[list(v) for v in result.trackAudit] if not matched else [],phys_audit=audit,clusters=list(result.clusters),longTracks=result.longTracks,sp=result.sp,spLinks=result.spLinks,spMissing=result.spMissing,measurements=result.measurements,measurementMissing=result.measurementMissing,rawMissing=result.rawMissing,invalidStrip=result.invalidStrip,invalidRaw=result.invalidRaw,invalidCluster=result.invalidCluster,duplicateClusterIdentifiers=result.duplicateClusterIdentifiers))
  if len(records)%100==0:print('NATIVE',index,len(records),flush=True)
  return PyAthena.StatusCode.Success
# Read only tracker-native objects. The historical REC waveform aux schema
# lacks trigger_time and is irrelevant here; do not instantiate NtupleDumper.
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from FaserActsKalmanFilter.MergeTracksConfig import MergeTrackCfg
flags=initConfigFlags();flags.Input.Files=paths;flags.Input.isMC=True
flags.IOVDb.DatabaseInstance='OFLP200';flags.Input.ProjectName='data21'
flags.GeoModel.FaserVersion='FASERNU-04';flags.IOVDb.GlobalTag='OFLCOND-FASER-06'
flags.Detector.GeometryFaserSCT=True;flags.Concurrency.NumThreads=0
flags.Exec.MaxEvents=len(cases);flags.Exec.OutputLevel=4;flags.lock()
acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.merge(MergeTrackCfg(flags))
excluded=[];left=0
for entry in entries:
 if left<entry:excluded.append(f'{left+1}-{entry}')
 left=entry+1
if left<source['parent_N']:excluded.append(f'{left+1}-{source["parent_N"]}')
acc.getService('EventSelector').SkipEventRanges=','.join(excluded)
acc.addEventAlgo(Snapshot('Stage124NativeAssociation'))
status=acc.run(maxEvents=len(cases));assert status.isSuccess()
assert len(records)==len(cases),(len(records),len(cases))
summary=dict(index=index,metadata=metadata,N=len(records),use_rec=True,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,read_bytes=int(__import__('ROOT').TFile.GetFileBytesRead()),records=records)
with gzip.open('result/native.json.gz','wt') as f:json.dump(summary,f,separators=(',',':'),allow_nan=True)
print('COMPLETE',index,len(records),summary['CPU_s'],summary['read_bytes'],flush=True)
