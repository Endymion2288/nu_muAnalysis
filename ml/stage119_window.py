"""Actual VetoNu geometry and digitizer-input time-window audit."""
import json
import resource
import time
from pathlib import Path


def main():
    from CalypsoConfiguration.AllConfigFlags import initConfigFlags
    from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
    from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
    from FaserGeoModel.ScintGMConfig import ScintGeometryCfg
    from AthenaPython import PyAthena
    root=Path(__file__).resolve().parents[1];out=root/'workbook/stage119_energy_ml'
    p=json.loads((out/'window_contract.json').read_text());flags=initConfigFlags()
    flags.Input.Files=[s['input'] for s in p['sources']];flags.Input.isMC=True
    flags.GeoModel.FaserVersion='FASERNU-04';flags.IOVDb.GlobalTag='OFLCOND-FASER-06'
    flags.Concurrency.NumThreads=0;flags.Exec.OutputLevel=4;flags.Exec.MaxEvents=-1;flags.lock()
    records=[];tick=time.perf_counter();cpu=time.process_time()
    class Inspect(PyAthena.Alg):
        def initialize(self):
            import ROOT
            assert ROOT.gInterpreter.Declare('''
#include "ScintReadoutGeometry/VetoNuDetectorManager.h"
#include "ScintReadoutGeometry/ScintDetectorElement.h"
#include "ScintSimEvent/ScintHit.h"
#include "StoreGate/StoreGateSvc.h"
#include "GaudiKernel/ServiceHandle.h"
double Stage119VetoNuZ(const ScintHit& hit) {
    ServiceHandle<StoreGateSvc> store("DetectorStore", "Stage119VetoNuZ");
    if (store.retrieve().isFailure()) throw std::runtime_error("DetectorStore unavailable");
    const ScintDD::VetoNuDetectorManager* det=nullptr;
    if (store->retrieve(det,"VetoNu").isFailure()) throw std::runtime_error("VetoNu geometry unavailable");
    return det->getDetectorElement(hit.getIdentifier())->center().z();
}
''')
            self.root=ROOT
            self.centers={}
            return PyAthena.StatusCode.Success
        def execute(self):
            store=PyAthena.py_svc('StoreGateSvc');info=store.retrieve('xAOD::EventInfo','EventInfo')
            hits=store.retrieve('ScintHitCollection','VetoNuHits');row=dict(run=int(info.runNumber()),eventID=int(info.eventNumber()),total_MeV=0.,inside_MeV=0.,early_MeV=0.,late_MeV=0.,hits=0)
            for h in hits:
                key=str(int(h.getStation()))+':'+str(int(h.getPlate()))
                if key not in self.centers:self.centers[key]=float(self.root.Stage119VetoNuZ(h))
                time_ns=float(h.meanTime())-self.centers[key]/299.792458
                e=float(h.energyLoss());row['total_MeV']+=e;row['hits']+=1
                row['early_MeV' if time_ns < -20 else 'late_MeV' if time_ns >= 1200 else 'inside_MeV']+=e
            records.append(row)
            return PyAthena.StatusCode.Success
    reader=Inspect('Stage119Window');acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.merge(ScintGeometryCfg(flags));acc.addEventAlgo(reader)
    assert acc.run().isSuccess()
    (out/'window2.json').write_text(json.dumps(dict(events=records,geometry='FASERNU-04',global_tag='OFLCOND-FASER-06',
        detector_centers_z_mm=reader.centers,input_window_ns=[-20,1200],sample_period_ns=2,samples=600,
        definition='VetoNu hit.meanTime - actual detector center.z/c; no scint propagation term for VetoNu in official tool; histogram acceptance only, not reconstructed late-charge efficiency',
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),separators=(',',':'))+'\n')


if __name__=='__main__':main()
