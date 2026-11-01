#!/usr/bin/env python3
"""Native POOL/HepMC audit. Never interpolate sparse vertices into plane truth."""
import argparse,json,math,time,resource
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--smoke',action='store_true');a=p.parse_args()
 request=json.loads(a.request.read_text());wanted={int(e['eventID']):e for e in request['events']};tick=time.perf_counter();cpu=time.process_time();results=[]
 from AthenaConfiguration.AllConfigFlags import initConfigFlags
 from AthenaConfiguration.MainServicesConfig import MainServicesCfg
 from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
 from AthenaPython import PyAthena
 import ROOT
 flags=initConfigFlags();flags.Input.Files=[request['row']['input_rdo']];flags.Concurrency.NumThreads=0;flags.Exec.OutputLevel=4
 flags.Exec.MaxEvents=1 if a.smoke else -1;flags.Exec.SkipEvents=min(e['entry'] for e in wanted.values()) if a.smoke else 0;flags.lock()
 def barcode(obj):return int(obj.attribute_as_string('barcode') or obj.id())
 def position(v,scale):return [float(getattr(v.position(),c)())*scale for c in ['x','y','z']] if v else None
 class Inspect(PyAthena.Alg):
  def execute(self):
   store=PyAthena.py_svc('StoreGateSvc');info=store.retrieve('xAOD::EventInfo','EventInfo');eid=int(info.eventNumber())
   if eid not in wanted:return PyAthena.StatusCode.Success
   old=wanted[eid];assert int(info.runNumber())==old['run']
   events=store.retrieve('McEventCollection','TruthEvent');assert events.size()==1;e=events[0]
   # Official GENIE reader and G4 InputConverter use internal MeV/mm numerics.
   # The saved HepMC enum can disagree; validate every primary against PHYS.
   scale=1.;length=1.
   muons=[part for part in e.particles() if int(part.pid())==int(old['primary_pdg'])]
   primary=[part for part in muons if barcode(part)==int(old['primary_barcode'])]
   row=dict(run=old['run'],eventID=eid,group=old['group'],index=int(request['row']['index']),primary_matches=len(primary),momentum_unit_to_MeV=scale,length_unit_to_mm=length,declared_momentum_unit=int(e.momentum_unit()),declared_length_unit=int(e.length_unit()),enum_MEV=int(ROOT.HepMC3.Units.MEV),enum_MM=int(ROOT.HepMC3.Units.MM),muon_records=len(muons),chain=[],ambiguity=False)
   if len(primary)==1:
    part=primary[0];row['generated_muon_mass_raw']=float(part.generated_mass());pm=[float(getattr(part.momentum(),c)())*scale for c in ['px','py','pz']]
    assert all(math.isclose(v,old['primary_'+c],rel_tol=2e-6,abs_tol=.01) for c,v in zip(['px','py','pz'],pm)),(eid,'production momentum',pm)
    pos=position(part.production_vertex(),length);assert all(abs(pos[i]-old[f'vertex_{c}_mm'])<.002 for i,c in enumerate(['x','y','z'])),(eid,'production vertex',pos)
    seen=set()
    while part:
     bc=barcode(part);assert bc not in seen;seen.add(bc)
     pm=[float(getattr(part.momentum(),c)())*scale/1000 for c in ['px','py','pz']]
     pv=part.production_vertex();ev=part.end_vertex()
     row['chain'].append(dict(barcode=bc,pdg=int(part.pid()),status=int(part.status()),p_GeV=math.sqrt(sum(v*v for v in pm)),p_xyz_GeV=pm,production_mm=position(pv,length),end_mm=position(ev,length)))
     if not ev:break
     children=[q for q in ev.particles_out() if int(q.pid())==int(old['primary_pdg'])]
     if len(children)>1:row['ambiguity']=True;break
     part=children[0] if children else None
    zref=old['reco_front'][2];zs=[v[2] for seg in row['chain'] for v in [seg['production_mm'],seg['end_mm']] if v is not None]
    row['nearest_saved_z_distance_mm']=min(abs(z-zref) for z in zs)
    row['saved_state_within_z_tolerance']=row['nearest_saved_z_distance_mm']<=request['cfg']['plane_tolerance_mm']
    row['finite_segment_spans_z']=sum(seg['production_mm'] is not None and seg['end_mm'] is not None and min(seg['production_mm'][2],seg['end_mm'][2])<=zref<=max(seg['production_mm'][2],seg['end_mm'][2]) for seg in row['chain'])
   results.append(row);print('AUDIT_EVENT',eid,'chain',len(row['chain']),flush=True)
   return PyAthena.StatusCode.Success
 acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.addEventAlgo(Inspect('AuditTransportTruth'));status=acc.run()
 if not status.isSuccess():raise RuntimeError('Native reader failed')
 if not a.smoke:assert {r['eventID'] for r in results}==set(wanted)
 result=dict(index=int(request['row']['index']),smoke=a.smoke,events=results,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,separators=(',',':'))+'\n');print('AUDIT_RESOURCES',json.dumps({k:v for k,v in result.items() if k!='events'}))

if __name__=='__main__':main()
