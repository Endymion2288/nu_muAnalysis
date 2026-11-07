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
with np.load(CACHE/f'pilot2_{index}.npz') as z:d={k:z[k] for k in z.files}
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
        records=[];controls=[]
        mapping={4:'VetoNu0',5:'VetoNu1',14:'Veto10',6:'Veto20',7:'Veto21'}
        names=d['names'].tolist();suffix=d['suffixes'].tolist()
        for i,row in enumerate(d['row']):
            for j,ch in enumerate(d['channel'][i]):
                if not d['present'][i,j]:continue
                channel=int(ch);name=mapping[channel];detector='VetoNu' if channel in [4,5] else 'Veto'
                identifier=int(d['id32'][i,j]);adc=d['adc'][i,j].astype(int)
                result=list(ROOT.Stage129Official(detector,channel,identifier,adc.tolist()))
                old=d['scalar'][i,names.index(name)]
                original=dict(row=int(row),channel=channel,name=name,official=result,
                              phys_status=float(old[suffix.index('status')]),phys_raw_pC=float(old[suffix.index('raw_charge')]),
                              phys_fit_pC=float(old[suffix.index('charge')]),phys_localtime_ns=float(old[suffix.index('localtime')]))
                records.append(original)
                if channel not in [6,7,14] or result[0]!=0 or (adc==0).any():continue
                baseline=result[3]*16.384/2
                peak=baseline-adc.min()
                if peak<20:continue
                for fraction in [.75,.5,.25]:
                    shift=int(np.floor(baseline-fraction*peak))
                    clipped=np.maximum(adc-shift,0)
                    fitted=list(ROOT.Stage129Official(detector,channel,identifier,clipped.tolist()))
                    start,stop=int(result[6]/2),int(result[7]/2)+1
                    assert result[6:8]==fitted[6:8]
                    target=float(.04*(result[3]*(stop-start)-adc[start:stop].sum()*2/16.384))
                    controls.append(dict(row=int(row),channel=channel,fraction=fraction,ADC_shift=shift,
                                         target_pC=target,original_official=result,clipped_official=fitted,
                                         clipped_samples=int((clipped[start:stop]==0).sum())))
        summary=dict(source=index,original=records,artificial_controls=controls,
                     artificial_definition='subtract integer pedestal shift then clip ADC at0; same real pulse/noise, known imposed lower rail; finite official W, not PMT nonlinear validation',
                     official_fields=['status','raw_pC','fit_pC','baseline_mV','baseline_rms_mV','internal_localtime_ns','window_start_ns','window_end_ns','peak_mV','mean_ns','width_ns','alpha','n'],
                     timing_policy='internal localtime is a charge-fit nuisance; any nonzero status never supplies model arrival time',
                     CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        (OUT/f'official_{index}.json').write_text(json.dumps(summary,indent=2)+'\n')
        print('OFFICIAL_CONTROLS',index,len(records),len(controls),flush=True)
        return PyAthena.StatusCode.Success


acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.merge(WaveformTimingCfg(flags))
for detector in ['VetoNu','Veto']:
    acc.addPublicTool(CompFactory.WaveformReconstructionTool('Stage129Rec'+detector,FitWindowWidth=100,BaselineSampleHi=60 if detector=='VetoNu' else 75))
acc.addEventAlgo(Snapshot('Stage129OfficialCharge'))
assert acc.run(maxEvents=1).isSuccess()
