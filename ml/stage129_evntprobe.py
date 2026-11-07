"""Read actual complete generator records from five retained exact EVNTs."""
import json,resource,sys,time
from pathlib import Path
from AthenaPython import PyAthena
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
import ROOT
import numpy as np
OUT=Path('workbook/stage129_energy_ml');index=int(sys.argv[1]);plan=json.loads((OUT/'parent_probe_protocol.json').read_text());extended=index>=10;source_index=index-10 if extended else index;path=plan['EVNT'][source_index]
tick,cpu=time.perf_counter(),time.process_time();records=[];counts={};scanned=0;oldkeys=set()
if extended:
 for filename in ['ntuples/energy_ml_stage119/old_input.npz','ntuples/energy_ml_stage119/curve_input.npz']:
  with np.load(filename) as z:oldkeys.update(tuple(r) for r in z['incoming'].astype('float32'))

class Snapshot(PyAthena.Alg):
 def execute(self):
  global scanned
  store=PyAthena.py_svc('StoreGateSvc');events=store.retrieve('McEventCollection','BeamTruthEvent');group=[]
  for event in events:
   particles=[];vertices=[]
   for p in event.particles():
    m=p.momentum();pv=p.production_vertex();ev=p.end_vertex()
    particles.append(dict(id=int(p.id()),pdg=int(p.pid()),status=int(p.status()),p=[m.px(),m.py(),m.pz(),m.e()],mass=p.generated_mass(),production_vertex=int(pv.id()) if pv else None,end_vertex=int(ev.id()) if ev else None))
   for v in event.vertices():
    p=v.position();vertices.append(dict(id=int(v.id()),position=[p.x(),p.y(),p.z(),p.t()],incoming=[int(x.id()) for x in v.particles_in()],outgoing=[int(x.id()) for x in v.particles_out()]))
   group.append(dict(event_number=event.event_number(),momentum_unit=str(event.momentum_unit()),length_unit=str(event.length_unit()),weights=list(event.weights()),particles=particles,vertices=vertices))
  entry=scanned;scanned+=1
  if extended:
   particles=group[0]['particles'];nu=[p for p in particles if abs(p['pdg'])==14 and p['status']==4];mu=[p for p in particles if abs(p['pdg'])==13 and p['status']==1]
   if len(nu)==1 and len(mu)==1:
    q,m=nu[0],mu[0];E=q['p'][3]/1000;pz=m['p'][2]/1000;y=1-m['p'][3]/q['p'][3]
    key=tuple(np.asarray([q['pdg']]+q['p'][:3],dtype='float32'));known=key in oldkeys
    counts['known_incoming']=counts.get('known_incoming',0)+known
    strata=['E50_100'] if 50<=E<100 else ['E100_200'] if 100<=E<200 else ['lowpz_highE'] if 50<=pz<100 and E>=200 else ['high_y'] if y>=.8 and pz>50 else ['highE'] if E>=1600 else ['transition'] if 200<=E<800 else []
    for layer in strata:
     counts[layer+'_all']=counts.get(layer+'_all',0)+1
     pos=group[0]['vertices'][0]['position'];fiducial=np.hypot(pos[0],pos[1])<100 and ((-3000<pos[2]<-1950) or (-1769.65<pos[2]<-1619.65))
     counts[layer+'_fiducial']=counts.get(layer+'_fiducial',0)+bool(fiducial and not known and pz>50)
     if not known and pz>50 and fiducial and counts.get(layer+'_retained',0)<3:
      counts[layer+'_retained']=counts.get(layer+'_retained',0)+1
      records.append(dict(entry=entry,events=group,stratum=layer,E_GeV=E,muon_pz_GeV=pz,y=y,known_old_incoming=False,source_index=source_index))
  else:records.append(dict(entry=entry,events=group))
  return PyAthena.StatusCode.Success
flags=initConfigFlags();flags.Input.Files=[path];flags.Input.isMC=True;flags.IOVDb.DatabaseInstance='OFLP200';flags.Input.ProjectName='data21';flags.GeoModel.FaserVersion='FASERNU-04';flags.IOVDb.GlobalTag='OFLCOND-FASER-06';flags.Concurrency.NumThreads=0;flags.Exec.MaxEvents=2048 if extended else 16;flags.Exec.OutputLevel=4;flags.lock()
a=MainServicesCfg(flags);a.merge(PoolReadCfg(flags));a.addEventAlgo(Snapshot('Stage129ActualGENIE'));assert a.run(2048 if extended else 16).isSuccess()
report=dict(path=path,scanned=scanned,counts=counts,records=records,old_exposure_status='uncertified: first16 content does not establish unexposed generator families',new_independent_selected_N=0,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
(OUT/f'evntprobe_{index}.json').write_text(json.dumps(report,indent=2)+'\n');print('EVNT_RECORDS',index,len(records),flush=True)
