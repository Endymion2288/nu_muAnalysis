"""Read pinned nominal GeoModel centre-line material intervals, not event labels."""
import json
import resource
import time
from pathlib import Path

import ROOT
from AthenaPython import PyAthena
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from FaserGeoModel.FaserGeoModelConfig import FaserGeometryCfg

OUT=Path('workbook/stage129_energy_ml')
plan=json.loads((OUT/'extraction_contract.json').read_text())
flags=initConfigFlags(); flags.Input.Files=[plan['requests'][0]['rdo']]; flags.Input.isMC=True
flags.IOVDb.DatabaseInstance='OFLP200'; flags.Input.ProjectName='data21'
flags.GeoModel.FaserVersion='FASERNU-04'; flags.IOVDb.GlobalTag='OFLCOND-FASER-06'
for detector in ['Emulsion','VetoNu','Veto','Trigger','Preshower','FaserSCT','Dipole','Ecal','Trench']:
    setattr(flags.Detector,'Geometry'+detector,True)
flags.Concurrency.NumThreads=0; flags.Exec.MaxEvents=1; flags.Exec.OutputLevel=4; flags.lock()
tick,cpu=time.perf_counter(),time.process_time()


class Snapshot(PyAthena.Alg):
    def execute(self):
        import StoreGateBindings.Bindings
        assert ROOT.gInterpreter.Declare(Path('ml/stage129_geometry.hxx').read_text())
        records=[]
        for row in ROOT.Stage129.centralMaterial():
            records.append(dict(volume=str(row.volume),material=str(row.material),low_mm=row.low,high_mm=row.high,
                                X0_mm=row.radiationLength,lambdaI_mm=row.interactionLength,
                                density_GeoModel_units=row.density,depth=row.depth))
        result=dict(geometry='FASERNU-04',tag='OFLCOND-FASER-06',commit='d32b0ff3',
                    definition='exact ray (x,y)=(0,0), z[-3200,-1300] mm through box volumes; use deepest material per segment; not event shower path',
                    intervals=records,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
                    RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        (OUT/'geometry_intervals.json').write_text(json.dumps(result,indent=2)+'\n')
        print('GEOMETRY_INTERVALS',len(records),flush=True)
        return PyAthena.StatusCode.Success


acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.merge(FaserGeometryCfg(flags))
acc.addEventAlgo(Snapshot('Stage129Geometry'))
assert acc.run(maxEvents=1).isSuccess()
