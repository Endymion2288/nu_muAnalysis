"""Native HITS observation audit; ancestry uncertainty is retained explicitly."""
import argparse
import json
import resource
import time
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p.add_argument('--events',type=int,default=1000);a=p.parse_args()
    from CalypsoConfiguration.AllConfigFlags import initConfigFlags
    from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
    from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
    from AthenaPython import PyAthena
    flags=initConfigFlags();flags.Input.Files=[a.input];flags.Input.isMC=True
    flags.Concurrency.NumThreads=0;flags.Exec.MaxEvents=a.events;flags.Exec.OutputLevel=4;flags.lock()
    rows=[];tick=time.perf_counter();cpu=time.process_time()
    def barcode(q):return int(q.attribute_as_string('barcode') or q.id())
    class Inspect(PyAthena.Alg):
        def execute(self):
            store=PyAthena.py_svc('StoreGateSvc');info=store.retrieve('xAOD::EventInfo','EventInfo')
            events=store.retrieve('McEventCollection','TruthEvent');assert events.size()==1
            event=events[0];parts=list(event.particles());by={barcode(q):q for q in parts}
            nus=[q for q in parts if abs(int(q.pid())) in [12,14,16] and int(q.status())==4]
            row=dict(run=int(info.runNumber()),eventID=int(info.eventNumber()),particles=len(parts),neutrino_N=len(nus),detectors={})
            if len(nus)==1:
                nu=nus[0];v=nu.end_vertex();mom=nu.momentum()
                row.update(incoming=[int(nu.pid())]+[float(getattr(mom,k)()) for k in ['px','py','pz']],E_GeV=float(mom.e())/1000)
                if v:
                    row.update(vertex_mm=[float(getattr(v.position(),k)()) for k in ['x','y','z']],vertex_time_ns=float(v.position().t())/299.792458)
                    primary=[q for q in v.particles_out() if int(q.pid())==int(nu.pid())*13/14]
                    row['primary_muon_N']=len(primary)
                    if len(primary)==1:row['y']=1-float(primary[0].momentum().e())/float(mom.e())
            def ancestry(q):
                seen=set();stack=[q];has_mu=False;complete=True;neutron=False
                while stack:
                    part=stack.pop();bc=barcode(part)
                    if bc in seen:continue
                    seen.add(bc);pid=abs(int(part.pid()));neutron |= pid==2112;has_mu |= pid==13
                    pv=part.production_vertex()
                    if not pv:
                        complete=False;continue
                    parents=list(pv.particles_in())
                    # A generator neutrino/nuclear vertex is an ancestry root;
                    # GENIE conversion has flattened the intranuclear graph.
                    if any(abs(int(x.pid())) in [12,14,16] for x in parents):continue
                    if not parents:complete=False
                    stack.extend(parents)
                return neutron,has_mu,complete
            for key in ['VetoNuHits','VetoHits','TriggerHits','PreshowerHits']:
                hits=store.retrieve('ScintHitCollection',key)
                # E-weighted moments avoid storing individual hit payloads.
                result=dict(hits=0,E_MeV=0.,mu_family_MeV=0.,known_nonmu_MeV=0.,unknown_family_MeV=0.,
                            neutron_ancestor_MeV=0.,neutron_unknown_MeV=0.,time_E_ns_MeV=0.,time2_E_ns2_MeV=0.,
                            min_time_ns=None,max_time_ns=None,linked_hits=0,plates={})
                for h in hits:
                    energy=float(h.energyLoss());t=float(h.meanTime());bc=int(h.trackNumber())
                    assert energy>=0
                    part=by.get(bc);result['hits']+=1;result['E_MeV']+=energy
                    result['time_E_ns_MeV']+=t*energy;result['time2_E_ns2_MeV']+=t*t*energy
                    result['min_time_ns']=t if result['min_time_ns'] is None else min(t,result['min_time_ns'])
                    result['max_time_ns']=t if result['max_time_ns'] is None else max(t,result['max_time_ns'])
                    plate=f'{int(h.getStation())}:{int(h.getPlate())}'
                    result['plates'][plate]=result['plates'].get(plate,0.)+energy
                    if part:
                        result['linked_hits']+=1;n,mu,complete=ancestry(part)
                        result['mu_family_MeV' if mu else 'known_nonmu_MeV' if complete else 'unknown_family_MeV']+=energy
                        if n:result['neutron_ancestor_MeV']+=energy
                        elif not complete:result['neutron_unknown_MeV']+=energy
                    else:
                        result['unknown_family_MeV']+=energy;result['neutron_unknown_MeV']+=energy
                row['detectors'][key]=result
            rows.append(row)
            return PyAthena.StatusCode.Success
    acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.addEventAlgo(Inspect('Stage119Hits'))
    status=acc.run();assert status.isSuccess()
    Path(a.output).write_text(json.dumps(dict(input=a.input,events=rows,CPU_s=time.process_time()-cpu,
        wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        units='native internal MeV/mm; G4 hit meanTime ns; HepMC vertex t length mm /c',
        ancestry='persisted TruthEvent only; absent particles/parents unknown; GENIE FSI graph not recovered'),separators=(',',':'))+'\n')


if __name__=='__main__':main()
