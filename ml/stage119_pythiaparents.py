"""Native full-parent HITS pilot, preserving zero/unknown and file probability."""
import argparse
import json
import resource
import time
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--index',type=int,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];out=root/'workbook/stage119_energy_ml'
    source=json.loads((out/'pythia_contract.json').read_text())['sources'][a.index]
    from CalypsoConfiguration.AllConfigFlags import initConfigFlags
    from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
    from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
    from AthenaPython import PyAthena
    flags=initConfigFlags();flags.Input.Files=[source['input']];flags.Input.isMC=True;flags.Concurrency.NumThreads=0;flags.Exec.OutputLevel=4;flags.lock()
    rows=[];tick=time.perf_counter();cpu=time.process_time()
    class Inspect(PyAthena.Alg):
        def execute(self):
            store=PyAthena.py_svc('StoreGateSvc');info=store.retrieve('xAOD::EventInfo','EventInfo');events=store.retrieve('McEventCollection','TruthEvent')
            assert events.size()==1
            parts=list(events[0].particles());nu=[q for q in parts if abs(int(q.pid())) in [12,14,16] and int(q.status())==4]
            row=dict(entry=len(rows),run=int(info.runNumber()),eventID=int(info.eventNumber()),nu_N=len(nu),eligible=False)
            assert row['run']==source['run']
            if len(nu)==1:
                n=nu[0];m=n.momentum();v=n.end_vertex();row['incoming']=[int(n.pid())]+[float(getattr(m,k)()) for k in ['px','py','pz']];row['E_GeV']=float(m.e())/1000
                if v:
                    x,y,z=[float(getattr(v.position(),k)()) for k in ['x','y','z']];row['vertex_mm']=[x,y,z]
                    row['eligible']=abs(int(n.pid()))==14 and float(m.pz())>50000 and x*x+y*y<10000 and (-3000<z<-1950 or -1769.65<z<-1619.65)
                    mu=[q for q in v.particles_out() if int(q.pid())==int(n.pid())*13/14]
                    row['mu_N']=len(mu)
                    if len(mu)==1:row['y']=1-float(mu[0].momentum().e())/float(m.e())
            rows.append(row);return PyAthena.StatusCode.Success
    acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.addEventAlgo(Inspect('Stage119PythiaParents'));assert acc.run().isSuccess()
    result=dict(source=source,parents=rows,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (out/f'pythia_parent_{a.index}.json').write_text(json.dumps(result,separators=(',',':'))+'\n')


if __name__=='__main__':main()
