"""Independent persistent-HITS energy closure for the live-step observer."""
import gzip
import json
import resource
import sys
import time
from pathlib import Path
import ROOT
from AthenaPython import PyAthena
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg

hits,lineage,output=map(Path,sys.argv[1:4]);observed=json.loads(lineage.read_text().strip());tick=time.perf_counter();results=[];snapshot={}
collections=[('ScintHitCollection','VetoNuHits','vetonu'),('ScintHitCollection','VetoHits','veto'),('ScintHitCollection','TriggerHits','trigger'),('ScintHitCollection','PreshowerHits','preshower'),('CaloHitCollection','EcalHits','ecal'),('FaserSiHitCollection','SCT_Hits','sct')]

class Check(PyAthena.Alg):
    def execute(self):
        sg=PyAthena.py_svc('StoreGateSvc')
        for typ,name,match in collections:
            coll=sg.retrieve(typ,name);energy=sum(float(h.energyLoss()) for h in coll)
            snapshot[name]=[[int(h.identify()),float(h.energyLoss()),float(h.meanTime()),
                int(h.trackNumber()),*map(float,[h.localStartPosition().x(),h.localStartPosition().y(),h.localStartPosition().z(),h.localEndPosition().x(),h.localEndPosition().y(),h.localEndPosition().z()])] for h in coll]
            keys=[k for k in observed['deposits'] if match in k.lower() and not (match=='veto' and 'vetonu' in k.lower())]
            # A zero-hit detector may not have appeared in the step observer.
            other=sum(sum(observed['deposits'][k]['all_MeV']) for k in keys)
            # P1a/P3a energy quantization is 1e-5MeV with cumulative rounding.
            # Per-hit half-quantum + float32 bound is conservative for each string.
            delta=abs(energy-other);tolerance=max(1e-6,len(coll)*5.1e-6+abs(energy)*2e-7)
            results.append(dict(collection=name,SD=keys,hits_N=len(coll),persistent_energy_MeV=energy,observer_energy_MeV=other,abs_delta_MeV=delta,tolerance_MeV=tolerance,passed=delta<=tolerance))
        return PyAthena.StatusCode.Success

flags=initConfigFlags();flags.Input.Files=[str(hits)];flags.Input.isMC=True;flags.Input.ProjectName='data21';flags.IOVDb.DatabaseInstance='OFLP200';flags.GeoModel.FaserVersion='FASERNU-04';flags.IOVDb.GlobalTag='OFLCOND-FASER-06';flags.Concurrency.NumThreads=0;flags.Exec.MaxEvents=1;flags.Exec.OutputLevel=4;flags.lock()
cfg=MainServicesCfg(flags);cfg.merge(PoolReadCfg(flags));cfg.addEventAlgo(Check('Stage131PersistentClosure'));assert cfg.run(1).isSuccess()
report=dict(passed=all(r['passed'] for r in results),rows=results,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,read_bytes=int(ROOT.TFile.GetFileBytesRead()))
if len(sys.argv)>4:
    mode,saved=sys.argv[4],Path(sys.argv[5])
    if mode=='before':
        with gzip.open(saved,'wt') as f:json.dump(snapshot,f,separators=(',',':'))
    else:
        with gzip.open(saved,'rt') as f:original=json.load(f)
        report['observer_on_off_sensitive_hits_exact']=original==snapshot
        assert report['observer_on_off_sensitive_hits_exact']
output.write_text(json.dumps(report,indent=2)+'\n');assert report['passed'],report
