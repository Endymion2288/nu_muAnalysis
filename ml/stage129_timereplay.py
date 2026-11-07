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
        records=[];closure=[]
        mapping={4:0,5:1,14:2,6:3,7:4}
        for ss in plan['requests'][index*14:(index+1)*14]:
            with np.load(f'/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage129/extract_{ss["index"]}.npz') as f:d={k:f[k] for k in f.files}
            start=len(records)
            for j,ch in enumerate(d['channel'][0]):
                channel=int(ch);col=mapping[channel];detector='VetoNu' if channel in [4,5] else 'Veto'
                for i,row in enumerate(d['row']):
                    if not d['present'][i,j] or d['scalar'][i,col,0]!=0:continue
                    r=list(ROOT.Stage129Official(detector,channel,int(d['id32'][i,j]),d['adc'][i,j].astype(int).tolist()))
                    # A failed replay cannot supply arrival time even when oldstatus was0.
                    records.append(dict(row=int(row),source=ss['index'],channel=channel,old_status=0,new_status=r[0],new_time_ns=r[5] if r[0]==0 else float('nan'),old_time_ns=float(d['scalar'][i,col,3]),new_raw_pC=r[1],old_raw_pC=float(d['scalar'][i,col,1])))
            block=records[start:]
            closure.append(dict(source=ss['index'],replays=len(block),new_status0=sum(r['new_status']==0 for r in block),raw_max_abs_pC=max((abs(r['new_raw_pC']-r['old_raw_pC']) for r in block),default=None),time_max_abs_ns=max((abs(r['new_time_ns']-r['old_time_ns']) for r in block if r['new_status']==0),default=None)))
        np.savez_compressed(CACHE/f'timereplay_{index}.npz',**{k:np.asarray([r[k] for r in records]) for k in records[0]})
        summary=dict(index=index,replays=len(records),sources=closure,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        (OUT/f'timereplay_{index}.json').write_text(json.dumps(summary,indent=2)+'\n')
        print('TIME_REPLAY',index,len(records),flush=True)
        return PyAthena.StatusCode.Success


acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.merge(WaveformTimingCfg(flags))
for detector in ['VetoNu','Veto']:
    acc.addPublicTool(CompFactory.WaveformReconstructionTool('Stage129Rec'+detector,FitWindowWidth=100,BaselineSampleHi=60 if detector=='VetoNu' else 75))
acc.addEventAlgo(Snapshot('Stage129OfficialCharge'))
assert acc.run(maxEvents=1).isSuccess()
