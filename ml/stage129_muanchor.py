"""Same pinned digitization/reconstruction prompt-muon reference; no nu labels."""
import json,resource,time,zlib
from pathlib import Path
import ROOT
from AthenaPython import PyAthena
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from AthenaConfiguration.ComponentFactory import CompFactory
from FaserGeoModel.ScintGMConfig import ScintGeometryCfg
from WaveformConditionsTools.WaveformDigitizationConfig import WaveformDigitizationCfg
from WaveformConditionsTools.WaveformTimingConfig import WaveformTimingCfg
from WaveformConditionsTools.WaveformCableMappingConfig import WaveformCableMappingCfg
OUT=Path('workbook/stage129_energy_ml');CACHE=Path('ntuples/energy_ml_stage129')
plan=json.loads((OUT/'muanchor_protocol.json').read_text());tick,cpu=time.perf_counter(),time.process_time();records=[];cabling={};conditions={}
class Snapshot(PyAthena.Alg):
 def initialize(self):
  import StoreGateBindings.Bindings
  assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n')
  for lib in ['libWaveRawEvent.so','libScintSimEvent.so','libxAODFaserWaveform.so']:assert ROOT.gSystem.Load(lib)>=0
  assert ROOT.gInterpreter.Declare(Path('ml/stage122_response.hxx').read_text());assert ROOT.gInterpreter.Declare(Path('ml/stage129_official.hxx').read_text());return PyAthena.StatusCode.Success
 def execute(self):
  store=PyAthena.py_svc('StoreGateSvc');info=store.retrieve('EventInfo','McEventInfo');event=int(info.event_ID().event_number())
  row=dict(entry=len(records),event=event,waves=[])
  truth=store.retrieve('McEventCollection','TruthEvent');particles=[p for p in truth[0].particles() if abs(p.pid())==13 and p.status() in [1,4]]
  if particles:
   p=max(particles,key=lambda p:p.momentum().pz());m=p.momentum();v=p.production_vertex();pos=v.position() if v else None
   row['muon']=[m.px(),m.py(),m.pz(),pos.x() if pos else float('nan'),pos.y() if pos else float('nan'),pos.z() if pos else float('nan')]
  for detector in ['VetoNu','Veto']:
   cable=[list(r) for r in ROOT.Stage122CableMap(detector)];cabling[detector]=cable;conditions[detector]=list(ROOT.Stage122Conditions(detector));idmap={int(r[1]):int(r[0]) for r in cable}
   hits=store.retrieve('ScintHitCollection',detector+'Hits');ROOT.Stage122Seed(detector,zlib.crc32(f'stage129mu:{event}:{detector}'.encode()) or 1)
   waves=ROOT.Stage122Digitize(detector,hits)
   for w in waves:
    id32=int(w[0])>>32;ch=idmap.get(id32)
    if ch not in [4,5,14,6,7]:continue
    result=list(ROOT.Stage129Official(detector,ch,id32,[int(x) for x in w[1:]]))
    row['waves'].append(dict(channel=ch,id32=id32,result=result))
  records.append(row);return PyAthena.StatusCode.Success
flags=initConfigFlags();flags.Input.Files=[plan['HITS']];flags.Input.isMC=True;flags.IOVDb.DatabaseInstance='OFLP200';flags.Input.ProjectName='data21';flags.GeoModel.FaserVersion='FASERNU-04';flags.IOVDb.GlobalTag='OFLCOND-FASER-06'
for detector in ['VetoNu','Veto','Preshower','Trigger']:setattr(flags.Detector,'Geometry'+detector,True)
flags.Concurrency.NumThreads=0;flags.Exec.MaxEvents=plan['events'];flags.Exec.OutputLevel=4;flags.lock();a=MainServicesCfg(flags);a.merge(PoolReadCfg(flags));a.merge(ScintGeometryCfg(flags));a.merge(WaveformDigitizationCfg(flags));a.merge(WaveformTimingCfg(flags));a.merge(WaveformCableMappingCfg(flags));a.addPublicTool(CompFactory.WaveformCableMappingTool('Stage122Cable'))
for detector in ['VetoNu','Veto']:
 a.addPublicTool(CompFactory.WaveformDigitisationTool('Stage122'+detector));a.addPublicTool(CompFactory.WaveformDigiConditionsTool('Stage122Cond'+detector,Detector=detector));a.addPublicTool(CompFactory.WaveformReconstructionTool('Stage129Rec'+detector,FitWindowWidth=100,BaselineSampleHi=60 if detector=='VetoNu' else 75))
a.addEventAlgo(Snapshot('Stage129MatchedMuon'));assert a.run(plan['events']).isSuccess()
report=dict(records=records,cabling=cabling,conditions=conditions,source=plan,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
(OUT/'muanchor.json').write_text(json.dumps(report,separators=(',',':'))+'\n');print('MATCHED_MU',len(records),flush=True)
