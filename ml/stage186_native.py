"""Batch-only original HITS, physical PMTs and signed same-window integrals."""
import json,os,resource,sys,time
from pathlib import Path
import numpy as np
import ROOT
from stage184_freeze import hit_paths
OUT=Path('workbook/stage186_energy_ml');CACHE=Path('ntuples/energy_ml_stage186')
plan=json.loads((OUT/'protocol.json').read_text());phase=sys.argv[1];group=int(sys.argv[2])
requests=json.loads(Path('workbook/stage129_energy_ml/extraction_contract.json').read_text())['requests']
proof={r['index']:r for r in json.loads((OUT/'source_producers.json').read_text())}
indices=plan['pilot']['source_indices'] if phase=='pilot' else [0] if phase=='repeat' else plan['production_groups'][group]
label=f'{phase}_{group}';sources=[];cases=[];counts=[];offset=0;cpu=time.process_time();tick=time.perf_counter()
for i in indices:
 s=dict(requests[i]);q=[c for c in s['cases'] if c['role']==1][:plan['pilot']['actual_train_N'][str(i)]] if phase=='pilot' else [c for c in s['cases'] if c['role']==1][:4] if phase=='repeat' else [c for c in s['cases'] if c['role']>0]
 if not q or not proof[i]['supported']:continue
 s['cases']=q;s['hits']=hit_paths(s);source_counts=[]
 for path in s['hits']:
  f=ROOT.TFile.Open(path);assert f and not f.IsZombie(),path
  tree=f.Get('CollectionTree');source_counts.append(dict(path=path,N=int(tree.GetEntries()) if tree else 0));f.Close()
 rdo_file=ROOT.TFile.Open(s['rdo']);assert rdo_file and not rdo_file.IsZombie();actual_N=int(rdo_file.Get('CollectionTree').GetEntries());rdo_file.Close()
 assert sum(r['N'] for r in source_counts)==actual_N,(i,source_counts,actual_N)
 assert all(0<=c['entry']<actual_N for c in q)
 s['declared_parent_N']=s['parent_N'];s['parent_N']=actual_N
 cases += [dict(c,source_index=i,global_entry=offset+c['entry']) for c in q];sources.append(s);counts+=source_counts;offset+=s['parent_N']
assert cases;entries=[c['global_entry'] for c in cases];assert entries==sorted(set(entries))
assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n')
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from AthenaConfiguration.ComponentFactory import CompFactory
from AthenaPython import PyAthena
from FaserGeoModel.ScintGMConfig import ScintGeometryCfg
from EcalGeoModel.EcalGeoModelConfig import EcalGeometryCfg
from WaveformConditionsTools.WaveformDigitizationConfig import WaveformDigitizationCfg
from WaveformConditionsTools.WaveformCableMappingConfig import WaveformCableMappingCfg
from WaveformConditionsTools.WaveformTimingConfig import WaveformTimingCfg
flags=initConfigFlags();flags.Input.Files=[r['path'] for r in counts if r['N']];flags.Input.isMC=True;flags.Input.ProjectName='data20';flags.IOVDb.DatabaseInstance='OFLP200'
flags.GeoModel.FaserVersion=plan['geometry'];flags.IOVDb.GlobalTag=plan['global_tag']
for d in ['VetoNu','Veto','Trigger','Preshower','Ecal']:setattr(flags.Detector,'Geometry'+d,True)
flags.Concurrency.NumThreads=0;flags.Exec.MaxEvents=len(cases);flags.Exec.SkipEvents=entries[0];flags.Exec.OutputLevel=4;flags.lock()
acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.merge(ScintGeometryCfg(flags));acc.merge(EcalGeometryCfg(flags));acc.merge(WaveformDigitizationCfg(flags));acc.merge(WaveformCableMappingCfg(flags));acc.merge(WaveformTimingCfg(flags))
acc.addPublicTool(CompFactory.WaveformCableMappingTool('Stage122Cable'))
detectors=['Calo','VetoNu','Veto','Trigger','Preshower'];expected={'Calo':[0,1,2,3],'VetoNu':[4,5],'Veto':[14,6,7],'Trigger':[8,9,10,11],'Preshower':[12,13]}
for d in detectors:
 acc.addPublicTool(CompFactory.WaveformDigiConditionsTool('Stage122Cond'+d,Detector=d))
 options={} if d=='Calo' else dict(FitWindowWidth=100,BaselineSampleHi=60 if d in ['VetoNu','Preshower'] else 75)
 acc.addPublicTool(CompFactory.WaveformReconstructionTool('Stage129Rec'+d,**options))
channels=plan['channels'];n=len(cases);shape=(n,15)
data=dict(row=np.array([c['row'] for c in cases]),entry=np.array([c['entry'] for c in cases]),source_index=np.array([c['source_index'] for c in cases]),run=np.array([c['run'] for c in cases]),event=np.array([c['event'] for c in cases]),role=np.array([c['role'] for c in cases]),incoming=np.array([c['incoming'] for c in cases],dtype='float32'),raw_pC=np.full(shape,np.nan),ideal_pC=np.full(shape,np.nan),status=np.full(shape,-1,np.int32),present=np.zeros(shape,bool),common=np.zeros(shape,bool),fit_invalid=np.full(shape,np.nan,'float32'),censor=np.full(shape,np.nan,'float32'),stored_id32=np.zeros(shape,np.uint32),current_id32=np.zeros(shape,np.uint32))
resources=[];literals=[];sourceinfo={};processed=0;old_raw_checks=0;rounding_records=[]
old_x=None;raw_columns={}
if phase=='full':
 with np.load('ntuples/energy_ml_stage119/old_input.npz') as z:old_x=z['x']
 old_names=json.loads(Path('ml/configs/audited_features.json').read_text())['features']
 scint=['VetoNu0','VetoNu1','Veto10','Veto20','Veto21']+[f'Timing{i}' for i in range(4)]+['Preshower0','Preshower1']
 raw_columns={ch:old_names.index(name+'_raw_charge') for ch,name in zip(channels[4:],scint)}
class Reader(PyAthena.Alg):
 def initialize(self):
  import StoreGateBindings.Bindings
  for lib in ['libIdentifier.so','libScintIdentifier.so','libScintReadoutGeometry.so','libFaserCaloSimEvent.so','libCaloReadoutGeometry.so','libWaveRawEvent.so','libScintSimEvent.so','libxAODFaserWaveform.so','libIdDict.so','libIdDictParser.so']:assert ROOT.gSystem.Load(lib)>=0,lib
  for header in ['stage138_response.hxx','stage144_ecal.hxx','stage129_official.hxx','stage141_analog.hxx','stage184_window.hxx','stage185_mapping.hxx','stage185_identity.hxx']:assert ROOT.gInterpreter.Declare(Path('ml',header).read_text()),header
  self.decoders={k:ROOT.Stage185Identity(v) for k,v in plan['dictionary_paths'].items()};self.saved=None;self.source_index=None;self.integrators={};self.maps={};return PyAthena.StatusCode.Success
 def execute(self):
  global processed,old_raw_checks
  begin=time.process_time();wall=time.perf_counter();b0=int(ROOT.TFile.GetFileBytesRead());c=cases[processed];s=requests[c['source_index']]
  if processed==0:self.startup_CPU_s=begin-cpu;self.startup_wall_s=wall-tick
  store=PyAthena.py_svc('StoreGateSvc');info=store.retrieve('xAOD::EventInfo','EventInfo');run,event=int(info.runNumber()),int(info.eventNumber());assert (run,event)==(c['run'],c['event'])
  truth=store.retrieve('McEventCollection','TruthEvent');assert truth.size()==1
  nu=[q for q in truth[0].particles() if abs(int(q.pid())) in [12,14,16] and int(q.status())==4];assert len(nu)==1
  m=nu[0].momentum();incoming=[int(nu[0].pid())]+[float(getattr(m,k)()) for k in ['px','py','pz']];np.testing.assert_array_equal(np.asarray(incoming,dtype='float32'),data['incoming'][processed])
  newsource=self.source_index!=s['index']
  if newsource:
   if self.saved:self.saved.file.Close()
   from stage122_saved import SavedWaveforms
   self.saved=SavedWaveforms(ROOT,s['rdo'],detectors);self.source_index=s['index'];self.maps={}
   sourceinfo[str(s['index'])]=dict(index=s['index'],N=sum(x['source_index']==s['index'] for x in cases),mappings={},conditions={})
  waves=self.saved.read(c['entry'],run,event);literalCPU=0.
  firsttwo=[q['row'] for q in next(x for x in sources if x['index']==s['index'])['cases'][:2]]
  do_literal=phase in ['pilot','repeat'] and c['row'] in firsttwo
  for detector in detectors:
   cond=list(ROOT.Stage122Conditions(detector));old=proof[s['index']]['kernel_parameters'][detector]
   np.testing.assert_allclose(cond[3:],[old[k] for k in ['Alpha','N','Sigma','Mean','Norm']],rtol=0,atol=1e-6)
   window=(390,465) if detector=='Calo' else (390,490);key=(detector,tuple(cond))
   if key not in self.integrators:self.integrators[key]=ROOT.Stage184Window(cond,*window)
   if detector not in self.maps:
    mapping=[list(r) for r in (ROOT.Stage185CaloMap() if detector=='Calo' else ROOT.Stage185ScintMap(detector))]
    self.maps[detector]=mapping;sourceinfo[str(s['index'])]['conditions'][detector]=cond
   mapping=self.maps[detector];bychannel={int(r[0]):r for r in mapping};byphysical={tuple(map(int,r[2:])):r for r in mapping} if detector!='Calo' else {}
   wavemap={w['channel']:w for w in waves[detector]};assert len(wavemap)==len(waves[detector])
   chosen={}
   for ch in expected[detector]:
    w=wavemap.get(ch)
    if w is None:continue
    if detector=='Calo':r=bychannel[ch];assert w['id32']==r[1]
    else:
     physical=list(self.decoders[proof[s['index']]['source_commit']].decode(w['id32']));assert physical[:2]==[2,dict(Veto=1,Trigger=2,Preshower=3,VetoNu=4)[detector]]
     r=byphysical[tuple(physical[2:])]
    chosen[ch]=r
    rec=dict(stored_id32=w['id32'],current_id32=int(r[1]),current_channel=int(r[0]),physical=list(map(int,r[2:])))
    existing=sourceinfo[str(s['index'])]['mappings'].get(str(ch));assert existing is None or existing==rec
    sourceinfo[str(s['index'])]['mappings'][str(ch)]=rec
   contributions=[list(r) for r in (ROOT.Stage144EcalTiming() if detector=='Calo' else ROOT.Stage138Timing(detector))]
   flat=[v for h in contributions for v in [h[0],h[3],h[1]]];ids=[int(r[1]) for r in chosen.values()]
   ideals={int(r[0]):float(r[1]) for r in self.integrators[key].integrate(flat,ids)}
   if do_literal and ids:
    start=time.process_time();a=np.asarray([list(r) for r in ROOT.Stage141Analog(flat,cond,ids,186000+s['index'],600)]);literalCPU+=time.process_time()-start
   for ch,r in chosen.items():
    j=channels.index(ch);w=wavemap[ch];actual=list(ROOT.Stage129Official(detector,ch,w['id32'],w['adc']));assert actual[6:8]==[window[0]*2.,window[1]*2.]
    raw=actual[1];ideal=ideals[int(r[1])];status=int(actual[0]);common=np.isfinite(raw) and np.isfinite(ideal) and not(status&392)
    assert np.isfinite(ideal) and ideal>=0
    if old_x is not None and ch in raw_columns and np.isfinite(old_x[c['row'],raw_columns[ch]]):
     if np.float32(raw)!=old_x[c['row'],raw_columns[ch]]:
      from stage186_rounding import certify
      rounding_records.append(certify(ROOT,s,c,ch,w['adc'],actual,old_x[c['row'],raw_columns[ch]]))
     old_raw_checks+=1
    data['raw_pC'][processed,j]=raw;data['ideal_pC'][processed,j]=ideal;data['status'][processed,j]=status;data['present'][processed,j]=True;data['common'][processed,j]=common
    data['fit_invalid'][processed,j]=bool(status&444);data['censor'][processed,j]=bool((status&4) or any(v in [0,16383] for v in w['adc'][window[0]:window[1]+1]))
    data['stored_id32'][processed,j]=w['id32'];data['current_id32'][processed,j]=int(r[1])
    if do_literal:
     use=(a[:,0]==r[1])&(a[:,1]>=window[0])&(a[:,1]<=window[1]);reference=float(a[use,2].sum()*(2*2000/16384/50));bound=32*np.finfo('float32').eps*max(1,abs(reference));assert abs(ideal-reference)<=bound
     literals.append(dict(row=c['row'],channel=ch,fast_pC=ideal,literal_pC=reference,abs_delta_pC=abs(ideal-reference),tolerance_pC=float(bound)))
  resources.append(dict(row=c['row'],source_index=s['index'],first_source_event=newsource,CPU_s=time.process_time()-begin,wall_s=time.perf_counter()-wall,literal_CPU_s=literalCPU,ROOT_requested_B=int(ROOT.TFile.GetFileBytesRead())-b0))
  processed+=1
  if processed%20==0 or newsource:print('STAGE186',label,processed,'/',n,resources[-1],flush=True)
  return PyAthena.StatusCode.Success
reader=Reader('Stage186OriginalReadout');acc.addEventAlgo(reader)
ranges=[f'{left+2}-{right}' for left,right in zip(entries,entries[1:]) if right>left+1]
if ranges:acc.getService('EventSelector').SkipEventRanges=','.join(ranges)
assert acc.run().isSuccess();assert processed==n
np.savez_compressed(CACHE/f'{label}.npz',**data)
result=dict(passed=True,phase=phase,group=group,N=n,source_N=len(sources),sources=list(sourceinfo.values()),HITS_counts=counts,literal_checks=literals,event_resources=resources,startup_CPU_s=reader.startup_CPU_s,startup_wall_s=reader.startup_wall_s,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,ROOT_requested_B=int(ROOT.TFile.GetFileBytesRead()),RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,raw11_old_feature_checks_N=old_raw_checks,baseline_rounding_records=rounding_records,energy_fits=0,new_G4=0,overall_complete=False)
(OUT/f'{label}_summary.json').write_text(json.dumps(result,indent=2)+'\n');print('COMPLETE',label,n,flush=True);sys.stdout.flush();sys.stderr.flush();os._exit(0)
