"""Exact official-tool original/ADC-clipped comparison on the frozen pilot."""
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import ROOT
from AthenaPython import PyAthena
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from AthenaConfiguration.ComponentFactory import CompFactory
from WaveformConditionsTools.WaveformTimingConfig import WaveformTimingCfg

OUT=Path('workbook/stage129_energy_ml');CACHE=Path('ntuples/energy_ml_stage129')
index=int(sys.argv[1]);plan=json.loads((OUT/'extraction_contract.json').read_text());source=plan['requests'][index]
with np.load(CACHE/'controls.npz') as z:d={k:z[k] for k in z.files}
tick,cpu=time.perf_counter(),time.process_time()
flags=initConfigFlags();flags.Input.Files=[source['rdo']];flags.Input.isMC=True
flags.IOVDb.DatabaseInstance='OFLP200';flags.Input.ProjectName='data21'
flags.GeoModel.FaserVersion='FASERNU-04';flags.IOVDb.GlobalTag='OFLCOND-FASER-06'
flags.Concurrency.NumThreads=0;flags.Exec.MaxEvents=1;flags.Exec.OutputLevel=4;flags.lock()


class Snapshot(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n')
        for lib in ['libWaveRawEvent.so','libxAODFaserWaveform.so']:
            assert ROOT.gSystem.Load(lib)>=0
        assert ROOT.gInterpreter.Declare(Path('ml/stage129_official.hxx').read_text())
        return PyAthena.StatusCode.Success

    def execute(self):
        records=[]
        for i in range(index,len(d['row']),4):
            channel=int(d['channel'][i]);identifier=int(d['id32'][i]);adc=d['adc'][i].astype(int)
            original=list(ROOT.Stage129Official('Veto',channel,identifier,adc.tolist()))
            assert original[6:8]==[780.,980.]
            base=adc[:75].mean();peak=base-adc.min()
            for fraction in [.75,.5,.25]:
                shift=int(np.floor(base-fraction*peak));clipped=np.maximum(adc-shift,0)
                result=list(ROOT.Stage129Official('Veto',channel,identifier,clipped.tolist()))
                assert result[6:8]==original[6:8]
                records.append(dict(control=i,row=int(d['row'][i]),source=int(d['source'][i]),role=int(d['role'][i]),channel=channel,fraction=fraction,
                    target_pC=original[1],raw_pC=result[1],CB_pC=result[2],CB_status=result[0],original_status=original[0],original_fit_pC=original[2],original_baseline_mV=original[3]))
        np.savez_compressed(CACHE/f'officialfull_{index}.npz',**{k:np.asarray([r[k] for r in records]) for k in records[0]})
        summary=dict(index=index,artificial_controls=len(records),original_controls=len(records)//3,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        (OUT/f'officialfull_{index}.json').write_text(json.dumps(summary,indent=2)+'\n')
        print('OFFICIAL_FULL',summary,flush=True)
        return PyAthena.StatusCode.Success


acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.merge(WaveformTimingCfg(flags))
for detector in ['VetoNu','Veto']:
    acc.addPublicTool(CompFactory.WaveformReconstructionTool('Stage129Rec'+detector,FitWindowWidth=100,BaselineSampleHi=60 if detector=='VetoNu' else 75))
acc.addEventAlgo(Snapshot('Stage129OfficialCharge'))
assert acc.run(maxEvents=1).isSuccess()
