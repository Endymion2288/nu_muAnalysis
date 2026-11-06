"""Read original HITS parent truth natively, retaining the complete denominator."""
import json
import sys
from pathlib import Path
root,index,limit=Path(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3])
source=json.loads((root/'workbook/stage125_energy_ml/protocol.json').read_text())['sources'][index]
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from AthenaPython import PyAthena
flags=initConfigFlags();flags.Input.Files=[source['input']];flags.Input.isMC=True
flags.Concurrency.NumThreads=0;flags.Exec.OutputLevel=4;flags.lock()
rows=[]
class Inspect(PyAthena.Alg):
    def execute(self):
        store=PyAthena.py_svc('StoreGateSvc');info=store.retrieve('xAOD::EventInfo','EventInfo')
        ev=store.retrieve('McEventCollection','TruthEvent');assert ev.size()==1
        nu=[p for p in ev[0].particles() if abs(int(p.pid())) in [12,14,16] and int(p.status())==4]
        assert len(nu)==1 and int(info.runNumber())==source['run']
        p=nu[0];m=p.momentum();v=p.end_vertex();keep=False
        incoming=[int(p.pid())]+[float(getattr(m,k)()) for k in ['px','py','pz']]
        if v:
            x,y,z=[float(getattr(v.position(),k)()) for k in ['x','y','z']]
            keep=abs(int(p.pid()))==14 and float(m.pz())>50000 and x*x+y*y<10000 and (-3000<z<-1950 or -1769.65<z<-1619.65)
        rows.append(dict(entry=len(rows),eventID=int(info.eventNumber()),incoming=incoming,keep=keep))
        return PyAthena.StatusCode.Success
acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.addEventAlgo(Inspect('Stage125Parents'))
assert acc.run(maxEvents=limit).isSuccess()
chosen=[r for r in rows if r['keep']]
request=dict(source=source,parent_N=len(rows),entries=[r['entry'] for r in chosen],
             eventID=[r['eventID'] for r in chosen],incoming=[r['incoming'] for r in chosen],rdo='input-RDO.root')
Path('request.json').write_text(json.dumps(request,separators=(',',':'))+'\n')
Path('result/request_summary.json').write_text(json.dumps({k:v for k,v in request.items() if k not in ['entries','eventID','incoming']},indent=2)+'\n')
