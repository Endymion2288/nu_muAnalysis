"""One retained HITS snapshot through real private digitizers; batch only."""
import gzip
import json
import resource
import sys
import time
from pathlib import Path
import numpy as np
import ROOT
from AthenaPython import PyAthena
from AthenaConfiguration.ComponentFactory import CompFactory
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from FaserGeoModel.ScintGMConfig import ScintGeometryCfg
from ScintDigiAlgs.ScintDigiAlgsConfig import ScintWaveformDigiCfg
from WaveformConditionsTools.WaveformDigitizationConfig import WaveformDigitizationCfg
from WaveformConditionsTools.WaveformCableMappingConfig import WaveformCableMappingCfg
from WaveformConditionsTools.WaveformTimingConfig import WaveformTimingCfg

OUT=Path('workbook/stage138_energy_ml');CACHE=Path('ntuples/energy_ml_stage138')
plan=json.loads((OUT/'protocol.json').read_text());case=plan['case'];replica=int(sys.argv[1])
with gzip.open('ntuples/energy_ml_stage135/parent_50_qa_hits.json.gz','rt') as f:snapshot=json.load(f)
with gzip.open('ntuples/energy_ml_stage131/pilot_private_rng_states.json.gz','rt') as f:original_rng=json.load(f)
records={};tick=time.perf_counter();cpu=time.process_time();rng={}
detectors=['VetoNu','Veto','Trigger','Preshower']

class Inject(PyAthena.Alg):
    def initialize(self):
        return PyAthena.StatusCode.Success
    def execute(self):
        for detector in detectors:
            ROOT.Stage138Record(detector,[value for row in snapshot[detector+'Hits'] for value in row])
            seed=original_rng[detector]['seed'];ROOT.Stage129PrivateSeed(detector,seed)
            state=str(ROOT.Stage129PrivateState(detector))
            assert state==original_rng[detector]['state'],(detector,'initial private state')
            rng[detector]=dict(seed=seed,before_exact=True)
        return PyAthena.StatusCode.Success

class Capture(PyAthena.Alg):
    def execute(self):
        store=PyAthena.py_svc('StoreGateSvc')
        for detector in detectors:
            after=str(ROOT.Stage129PrivateState(detector))
            assert after==original_rng[detector]['after'],(detector,'final private state')
            rng[detector]['after_exact']=True
            waves=[]
            for wave in store.retrieve('RawWaveformContainer',detector+'Waveforms'):
                adc=[int(x) for x in wave.adc_counts()];id32=int(wave.identify32().get_compact());channel=int(wave.channel())
                result=list(ROOT.Stage129Official(detector,channel,id32,adc))
                waves.append(dict(channel=channel,id32=id32,adc=adc,result=result))
            records[detector]=dict(waves=waves,timing=[list(r) for r in ROOT.Stage138Timing(detector)],
                conditions=list(ROOT.Stage122Conditions(detector)),
                cable_map=[list(r) for r in ROOT.Stage122CableMap(detector)])
        return PyAthena.StatusCode.Success

flags=initConfigFlags();flags.Input.Files=[case['EVNT']];flags.Input.isMC=True
# Match the original simulation's filename-derived EventID override, rather
# than using the EVNT generator's run/IOV for digitizer and cabling conditions.
flags.Input.RunNumbers=[990131];flags.Input.OverrideRunNumber=True
flags.Input.LumiBlockNumbers=[51];flags.Input.TimeStamps=[0]
flags.addFlag('Input.InitialTimeStamp',0)
flags.IOVDb.DatabaseInstance='OFLP200';flags.Input.ProjectName='data21'
flags.GeoModel.FaserVersion='FASERNU-04';flags.IOVDb.GlobalTag='OFLCOND-FASER-06'
for detector in detectors:setattr(flags.Detector,'Geometry'+detector,True)
flags.Concurrency.NumThreads=0;flags.Exec.MaxEvents=1;flags.Exec.SkipEvents=case['entry'];flags.Exec.OutputLevel=4;flags.lock()
acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags));acc.merge(ScintGeometryCfg(flags))
acc.merge(WaveformDigitizationCfg(flags));acc.merge(WaveformCableMappingCfg(flags));acc.merge(WaveformTimingCfg(flags))
acc.addPublicTool(CompFactory.WaveformCableMappingTool('Stage122Cable'))
acc.addEventAlgo(Inject('Stage138SnapshotAndActualPrivateSeeds'))
for detector in detectors:
    acc.addPublicTool(CompFactory.WaveformDigiConditionsTool('Stage122Cond'+detector,Detector=detector))
    acc.addPublicTool(CompFactory.WaveformReconstructionTool('Stage129Rec'+detector,FitWindowWidth=100,
                       BaselineSampleHi=60 if detector in ['VetoNu','Preshower'] else 75))
    acc.merge(ScintWaveformDigiCfg(flags,detector+'WaveformDigiAlg',detector,
              WaveformDigitisationTool=CompFactory.WaveformDigitisationTool('Stage122'+detector)))
acc.addEventAlgo(Capture('Stage138CaptureActualADC'))
import StoreGateBindings.Bindings
assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n')
for lib in ['libIdentifier.so','libScintIdentifier.so','libScintReadoutGeometry.so',
            'libWaveRawEvent.so','libScintSimEvent.so','libxAODFaserWaveform.so']:
    assert ROOT.gSystem.Load(lib)>=0,lib
for header in ['stage138_response.hxx','stage129_rng.hxx','stage129_official.hxx']:
    assert ROOT.gInterpreter.Declare(Path('ml',header).read_text()),header
assert acc.run(1).isSuccess()
(OUT/f'context_{replica}.json').write_text(json.dumps(dict(
    original_producer_context=dict(run=990131,lumiblock=51,timestamp=0),
    geometry='FASERNU-04',global_tag='OFLCOND-FASER-06',
    conditions={k:v['conditions'] for k,v in records.items()},
    channels={k:[w['channel'] for w in v['waves']] for k,v in records.items()},
    rng=rng),indent=2)+'\n')
with np.load('ntuples/energy_ml_stage131/matched_input.npz') as f:
    row=np.flatnonzero(f['frame_index']==50);assert len(row)==1
    target=f['raw_charge'][row[0]];status=f['status'][row[0]]
channels=[4,5,14,6,7,8,9,10,11,12,13];actual={r['channel']:r for d in records.values() for r in d['waves']}
checks=[]
for j,ch in enumerate(channels):
    if ch not in actual:
        detector='VetoNu' if j<2 else 'Veto' if j<5 else 'Trigger' if j<9 else 'Preshower'
        assert not snapshot[detector+'Hits'] and not records[detector]['waves'],(ch,'unexpected missing readout')
        # Original NtupleDumper ClearEvent defaults: raw=0,status=1. No ADC or
        # arrival time exists; preserve that distinction from a measured zero.
        assert target[j]==0 and status[j]==1,(ch,target[j],status[j],'original no-hit defaults')
        checks.append(dict(channel=ch,present=False,raw_pC=None,original_raw_pC=float(target[j]),
            delta_pC=0.,status=None,original_status=int(status[j]),window_ns=None,
            no_hit_producer_defaults_exact=True))
        continue
    result=actual[ch]['result'];delta=float(result[1]-target[j])
    # PHYS branch stores float32 while primary tool reports a double /50.
    assert np.float32(result[1])==np.float32(target[j]),(ch,result[1],target[j])
    assert int(result[0])==int(status[j]),(ch,result[0],status[j])
    assert result[6:8]==[780.,980.],(ch,result[6:8])
    checks.append(dict(channel=ch,present=True,raw_pC=result[1],original_raw_pC=float(target[j]),delta_pC=delta,status=int(result[0]),original_status=int(status[j]),window_ns=result[6:8]))
output=dict(records=records,rng=rng,raw_checks=checks,snapshot_fields_exact=True,
            frame_index=50,replica=replica,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
            ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            scope='one natural mu-root-only downstream control; EVNT only supplies event context; exact private RNG and raw11 required; no general ancestry/tail calibration')
with gzip.open(CACHE/f'control_{replica}.json.gz','wt') as f:json.dump(output,f,separators=(',',':'))
print('CONTROL',replica,checks,flush=True)
