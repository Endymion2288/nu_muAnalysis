"""One exact cached parent through all original digitizers and matched windows."""
import csv
import gzip
import json
import os
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
from EcalGeoModel.EcalGeoModelConfig import EcalGeometryCfg
from ScintDigiAlgs.ScintDigiAlgsConfig import ScintWaveformDigiCfg
from CaloDigiAlgs.CaloDigiAlgsConfig import CaloWaveformDigiCfg
from WaveformConditionsTools.WaveformDigitizationConfig import WaveformDigitizationCfg
from WaveformConditionsTools.WaveformCableMappingConfig import WaveformCableMappingCfg
from WaveformConditionsTools.WaveformTimingConfig import WaveformTimingCfg

OUT = Path('workbook/stage179_energy_ml')
CACHE = Path('ntuples/energy_ml_stage179')
index = int(sys.argv[1])
start = time.perf_counter()
with gzip.open('ntuples/energy_ml_stage131/production_cases.json.gz', 'rt') as stream:
    case = next(r for r in json.load(stream) if r['frame_index'] == index)
assert case['role'] == 1
with gzip.open(CACHE/f'parent_{index}_qa_hits.json.gz', 'rt') as stream:
    snapshot = json.load(stream)
with gzip.open(CACHE/f'parent_{index}_lineage.json.gz', 'rt') as stream:
    lineage = json.load(stream)
interval = json.loads((OUT/f'parent_{index}_intervals.json').read_text())
source_tags = {0:'primary_muon_direct', -1:'other_root', -2:'unknown_root'}
source_tags.update({r['group']:r['side'] for r in interval['births']})
categories = ['primary_muon_direct', 'before_S0', 'after_S0', 'other_root', 'unknown_root', 'unknown_S0']
detectors = ['Calo', 'VetoNu', 'Veto', 'Trigger', 'Preshower']
collection = dict(Calo='EcalHits', **{d:d+'Hits' for d in detectors[1:]})
original = None
if index == 50:
    with gzip.open('ntuples/energy_ml_stage131/pilot_private_rng_states.json.gz', 'rt') as stream:
        original = json.load(stream)
seeds = {d:original[d]['seed'] if original else 650000000+10000*index+1000*j for j,d in enumerate(detectors)}
records = {}; rng = {}

class Inject(PyAthena.Alg):
    def execute(self):
        ROOT.Stage144RecordEcal([v for row in snapshot['EcalHits'] for v in row])
        for detector in detectors[1:]:
            ROOT.Stage138Record(detector, [v for row in snapshot[collection[detector]] for v in row])
        for detector in detectors:
            ROOT.Stage129PrivateSeed(detector, seeds[detector])
            state = str(ROOT.Stage129PrivateState(detector))
            if original:
                assert state == original[detector]['state']
            rng[detector] = dict(seed=seeds[detector], initial_state_characters=len(state), original_initial_exact=bool(original) if original else None)
        return PyAthena.StatusCode.Success

class Capture(PyAthena.Alg):
    def execute(self):
        store = PyAthena.py_svc('StoreGateSvc')
        for detector in detectors:
            after = str(ROOT.Stage129PrivateState(detector))
            if original:
                assert after == original[detector]['after']
            rng[detector].update(after_state_characters=len(after), original_final_exact=bool(original) if original else None)
            waves = []
            for wave in store.retrieve('RawWaveformContainer', detector+'Waveforms'):
                adc = [int(v) for v in wave.adc_counts()]
                identifier = int(wave.identify32().get_compact()); channel = int(wave.channel())
                result = list(ROOT.Stage129Official(detector, channel, identifier, adc))
                waves.append(dict(channel=channel, id32=identifier, adc=adc, result=result))
            timing = [list(r) for r in (ROOT.Stage144EcalTiming() if detector=='Calo' else ROOT.Stage138Timing(detector))]
            tags = lineage['daq_birth_groups'].get(collection[detector], [])
            assert len(tags) == len(snapshot[collection[detector]])
            assert len(timing) == len(tags)*(2 if detector=='Trigger' else 1)
            for i, row in enumerate(timing):
                row.append(source_tags[tags[i//2 if detector=='Trigger' else i]])
            records[detector] = dict(waves=waves, source_timing=timing, conditions=list(ROOT.Stage122Conditions(detector)),
                all_geometry_PMTS=list(ROOT.Stage144EcalIdentifiers()) if detector=='Calo' else sorted(w['id32'] for w in waves))
        return PyAthena.StatusCode.Success

flags = initConfigFlags()
flags.Input.Files = [case['EVNT']]; flags.Input.isMC = True
flags.Input.RunNumbers = [990131]; flags.Input.OverrideRunNumber = True
flags.Input.LumiBlockNumbers = [index+1]; flags.Input.TimeStamps = [0]
flags.addFlag('Input.InitialTimeStamp', 0)
flags.Input.ProjectName = 'data21'; flags.IOVDb.DatabaseInstance = 'OFLP200'
flags.GeoModel.FaserVersion = 'FASERNU-04'; flags.IOVDb.GlobalTag = 'OFLCOND-FASER-06'
for detector in detectors[1:]:
    setattr(flags.Detector, 'Geometry'+detector, True)
flags.Detector.GeometryEcal = True
flags.Concurrency.NumThreads = 0; flags.Exec.MaxEvents = 1; flags.Exec.SkipEvents = case['entry']; flags.Exec.OutputLevel = 4
flags.lock()
acc = MainServicesCfg(flags); acc.merge(PoolReadCfg(flags))
acc.merge(ScintGeometryCfg(flags)); acc.merge(EcalGeometryCfg(flags))
acc.merge(WaveformDigitizationCfg(flags)); acc.merge(WaveformCableMappingCfg(flags)); acc.merge(WaveformTimingCfg(flags))
acc.addPublicTool(CompFactory.WaveformCableMappingTool('Stage122Cable'))
for detector in detectors:
    acc.addPublicTool(CompFactory.WaveformDigiConditionsTool('Stage122Cond'+detector, Detector=detector))
    options = {} if detector=='Calo' else dict(FitWindowWidth=100, BaselineSampleHi=60 if detector in ['VetoNu','Preshower'] else 75)
    acc.addPublicTool(CompFactory.WaveformReconstructionTool('Stage129Rec'+detector, **options))
acc.addEventAlgo(Inject('Stage179InjectExactPersistentHits'))
acc.merge(CaloWaveformDigiCfg(flags, WaveformDigitisationTool=CompFactory.WaveformDigitisationTool('Stage122Calo')))
for detector in detectors[1:]:
    acc.merge(ScintWaveformDigiCfg(flags, detector+'WaveformDigiAlg', detector,
        WaveformDigitisationTool=CompFactory.WaveformDigitisationTool('Stage122'+detector)))
acc.addEventAlgo(Capture('Stage179CaptureMatchedReadout'))
import StoreGateBindings.Bindings
assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n')
for library in ['libIdentifier.so', 'libScintIdentifier.so', 'libScintReadoutGeometry.so', 'libFaserCaloSimEvent.so',
    'libCaloReadoutGeometry.so', 'libWaveRawEvent.so', 'libScintSimEvent.so', 'libxAODFaserWaveform.so']:
    assert ROOT.gSystem.Load(library) >= 0
for header in ['stage138_response.hxx', 'stage129_rng.hxx', 'stage129_official.hxx', 'stage144_ecal.hxx', 'stage141_analog.hxx']:
    assert ROOT.gInterpreter.Declare(Path('ml', header).read_text()), header
assert acc.run(1).isSuccess()

with np.load('ntuples/energy_ml_stage131/matched_input.npz') as data:
    selected = np.flatnonzero(data['frame_index']==index)
    assert len(selected) <= 1
    reference = {k:data[k][selected[0]].tolist() for k in ['raw_charge', 'status', 'calo_status']} if len(selected) else None
    diagnostic = dict(truth_E_GeV=float(data['truth_E_GeV'][selected[0]]), pz0_GeV=float(data['pz'][selected[0]])) if len(selected) else None
    if diagnostic:
        with np.load('ml/artifacts/stage131/energy_predictions.npz') as predictions:
            diagnostic.update({arm+'_relative_error':float(np.exp(predictions[arm][selected[0]])/diagnostic['truth_E_GeV']-1) for arm in ['direct_cal','traditional']})
channels = [4,5,14,6,7,8,9,10,11,12,13]
actual = {w['channel']:w for d in records.values() for w in d['waves']}
if reference:
    for j, channel in enumerate(channels):
        if channel in actual:
            assert np.float32(actual[channel]['result'][1]) == np.float32(reference['raw_charge'][j])
            assert int(actual[channel]['result'][0]) == int(reference['status'][j])
        else:
            assert reference['raw_charge'][j] == 0 and reference['status'][j] == 1
    for wave in records['Calo']['waves']:
        assert int(wave['result'][0]) == int(reference['calo_status'][wave['channel']])

charges = []; analog_cache = {}; adc_samples = adc_mismatch = clipped = 0; max_additivity = 0.
convert = 2*2/16384/50*1000
for detector, record in records.items():
    waves = record['waves']
    if not waves:
        continue
    ids = record['all_geometry_PMTS']; n = len(waves[0]['adc'])
    full = [v for row in record['source_timing'] for v in [row[0], row[3], row[1]]]
    total = np.asarray([list(r) for r in ROOT.Stage141Analog(full, record['conditions'], ids, seeds[detector], n)])
    split = {}
    for category in categories:
        inputs = [v for row in record['source_timing'] if row[-1]==category for v in [row[0],row[3],row[1]]]
        split[category] = np.asarray([list(r) for r in ROOT.Stage141Analog(inputs, record['conditions'], ids, seeds[detector], n)])[:,2]
    delta = np.abs(sum(split.values())-total[:,2])
    assert np.all(delta <= 32*np.finfo('float32').eps*np.maximum(1, np.abs(total[:,2])))
    max_additivity = max(max_additivity, float(delta.max()))
    for wave in waves:
        rows = total[:,0] == wave['id32']
        adc = np.asarray(wave['adc']); prediction = total[rows,5].astype(int)
        adc_mismatch += int(np.sum(adc != prediction)); adc_samples += len(adc); clipped += int(np.sum(adc==0))
        assert np.array_equal(adc, prediction)
        a,b = wave['result'][6:8]
        assert [a,b] == ([780.,930.] if detector=='Calo' else [780.,980.])
        use = rows & (2*total[:,1] >= a) & (2*total[:,1] <= b)
        signal = total[use,2]; amp = total[use,3]; baseline = total[use,4]; digital = total[use,5]
        unrounded = baseline-amp
        # The pinned C++ digitizer subtracts two floats BEFORE std::round.
        digital_input = (baseline.astype('float32')-amp.astype('float32')).astype(float)
        unlimited = np.where(digital_input >= 0, np.floor(digital_input+.5), np.ceil(digital_input-.5))
        pedestal = record['conditions'][0]
        fitted = wave['result'][3]/(2000/16384)
        # Official stores float waveform samples and float raw integral.
        wwave = (np.float32(wave['result'][3])-np.float32(2000/16384)*digital.astype('float32')).astype('float32')
        manual = float(np.float32(2*wwave.astype(float).sum()))/50
        assert np.float32(manual*50) == np.float32(wave['result'][1]*50), (index,detector,wave['channel'],manual,wave['result'][1])
        pieces = dict(signal_pC=convert*signal.sum(), float_amplitude_pC=convert*(amp-signal).sum(),
            noise_pC=convert*(pedestal-baseline).sum(), rounding_pC=convert*(unrounded-unlimited).sum(),
            clipping_pC=convert*(unlimited-digital).sum(), pedestal_error_pC=convert*len(signal)*(fitted-pedestal))
        reconstructed = sum(pieces.values())
        assert abs(reconstructed-convert*(fitted-digital).sum()) < 1e-8*max(1, abs(reconstructed))
        source_values = {category+'_pC':float(convert*values[use].sum()) for category,values in split.items()}
        charges.append(dict(index=index,detector=detector,channel=wave['channel'],status=int(wave['result'][0]),
            window_start_ns=a,window_end_ns=b,actual_signed_raw_pC=wave['result'][1],
            no_clip_same_noise_pC=float(convert*(fitted-unlimited).sum()),
            ideal_no_noise_no_clip_no_quantization_pC=float(pieces['signal_pC']),
            raw_float_storage_delta_pC=float(wave['result'][1]-reconstructed),
            **{k:float(v) for k,v in pieces.items()}, **source_values))
    analog_cache[detector] = dict(total=total.tolist(), split={k:v.tolist() for k,v in split.items()})
with (OUT/f'parent_{index}_charges.tsv').open('w') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(charges[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(charges)
summary = dict(passed=True,index=index,ADC_samples=adc_samples,ADC_mismatch=adc_mismatch,clipped_samples=clipped,
    channels_N=len(charges),original_selected_reference_available=reference is not None,
    original_raw11_status_exact=True if reference else None,original_calo_status_exact=True if reference else None,
    original_calo_raw_reference_available=False,original_full_private_states_exact=bool(original),
    max_analog_additivity_delta_ADC=max_additivity,all_manual_raw_exact=True,diagnostic=diagnostic,
    wall_s=time.perf_counter()-start,ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),
    RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,new_G4=0,energy_fits=0,new_forward=0,overall_complete=False)
(OUT/f'parent_{index}_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
with gzip.open(CACHE/f'parent_{index}_response.json.gz','wt') as stream:
    json.dump(dict(records=records, rng=rng, analog=analog_cache, summary=summary),stream,separators=(',',':'))
print(summary,flush=True)
# Official runtime finalization can crash after successful output on lxplus; preserve measured success like Stage144.
sys.stdout.flush();sys.stderr.flush();os._exit(0)
