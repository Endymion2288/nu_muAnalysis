"""Ecal digitizer/source response control from retained snapshots, batch only."""
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
from EcalGeoModel.EcalGeoModelConfig import EcalGeometryCfg
from CaloDigiAlgs.CaloDigiAlgsConfig import CaloWaveformDigiCfg
from WaveformConditionsTools.WaveformDigitizationConfig import WaveformDigitizationCfg
from WaveformConditionsTools.WaveformCableMappingConfig import WaveformCableMappingCfg
from WaveformConditionsTools.WaveformTimingConfig import WaveformTimingCfg

STAGE = int(os.environ.get('NU_MU_ECAL_STAGE', '144'))
OUT = Path(f'workbook/stage{STAGE}_energy_ml')
CACHE = Path(f'ntuples/energy_ml_stage{STAGE}')
index = int(sys.argv[1])
plan = json.loads((OUT/'protocol.json').read_text())
assert index in plan['indices']
with gzip.open('ntuples/energy_ml_stage131/production_cases.json.gz', 'rt') as stream:
    case = next(row for row in json.load(stream) if row['frame_index'] == index)
if plan.get('snapshot_layout') == 'separate':
    with gzip.open(CACHE/f'parent_{index}_qa_hits.json.gz', 'rt') as stream:
        snapshot = json.load(stream)
    lineage = json.loads((OUT/f'parent_{index}_lineage.json').read_text())
else:
    with gzip.open('ntuples/energy_ml_stage142/event_records.json.gz', 'rt') as stream:
        retained = json.load(stream)
    snapshot = json.loads(retained[f'ntuples/energy_ml_stage142/parent_{index}_qa_hits.json.gz'])
    lineage = json.loads(retained[f'workbook/stage142_energy_ml/parent_{index}_lineage.json'])
assert case['role'] == 1
seed = 650000000+10000*index
if index == 50:
    with gzip.open('ntuples/energy_ml_stage131/pilot_private_rng_states.json.gz', 'rt') as stream:
        original = json.load(stream)['Calo']
    seed = original['seed']
else:
    original = None
tick, cpu = time.perf_counter(), time.process_time()
records = {}


class Inject(PyAthena.Alg):
    def execute(self):
        ROOT.Stage144RecordEcal([v for row in snapshot['EcalHits'] for v in row])
        ROOT.Stage129PrivateSeed('Calo', seed)
        records['initial_state'] = str(ROOT.Stage129PrivateState('Calo'))
        if original:
            assert records['initial_state'] == original['state']
        return PyAthena.StatusCode.Success


class Capture(PyAthena.Alg):
    def execute(self):
        records['final_state'] = str(ROOT.Stage129PrivateState('Calo'))
        if original:
            assert records['final_state'] == original['after']
        store = PyAthena.py_svc('StoreGateSvc')
        waves = []
        for wave in store.retrieve('RawWaveformContainer', 'CaloWaveforms'):
            adc = [int(value) for value in wave.adc_counts()]
            id32, channel = int(wave.identify32().get_compact()), int(wave.channel())
            result = list(ROOT.Stage129Official('Calo', channel, id32, adc))
            waves.append(dict(channel=channel, id32=id32, adc=adc, result=result))
        timing = [list(row) for row in ROOT.Stage144EcalTiming()]
        tags = lineage['daq_hits'].get('EcalHits', [])
        assert len(tags) == len(snapshot['EcalHits']) == len(timing)
        for tag, row in zip(tags, snapshot['EcalHits']):
            assert tag[4] == row[0] and tag[7] == row[3]
        records.update(waves=waves, source_timing=[row+[int(tag[0])] for row, tag in zip(timing, tags)],
                       conditions=list(ROOT.Stage122Conditions('Calo')),
                       all_geometry_PMTS=list(ROOT.Stage144EcalIdentifiers()))
        return PyAthena.StatusCode.Success


flags = initConfigFlags()
flags.Input.Files = [case['EVNT']]
flags.Input.isMC = True
flags.Input.RunNumbers = [990131]
flags.Input.OverrideRunNumber = True
flags.Input.LumiBlockNumbers = [index+1]
flags.Input.TimeStamps = [0]
flags.addFlag('Input.InitialTimeStamp', 0)
flags.IOVDb.DatabaseInstance = 'OFLP200'
flags.Input.ProjectName = 'data21'
flags.GeoModel.FaserVersion = 'FASERNU-04'
flags.IOVDb.GlobalTag = 'OFLCOND-FASER-06'
flags.Detector.GeometryEcal = True
flags.Concurrency.NumThreads = 0
flags.Exec.MaxEvents = 1
flags.Exec.SkipEvents = case['entry']
flags.Exec.OutputLevel = 4
flags.lock()
acc = MainServicesCfg(flags)
acc.merge(PoolReadCfg(flags))
acc.merge(EcalGeometryCfg(flags))
acc.merge(WaveformDigitizationCfg(flags))
acc.merge(WaveformCableMappingCfg(flags))
acc.merge(WaveformTimingCfg(flags))
acc.addPublicTool(CompFactory.WaveformDigiConditionsTool('Stage122CondCalo', Detector='Calo'))
# Calo reconstruction uses production defaults, unlike the scintillator 100 ns fit window.
acc.addPublicTool(CompFactory.WaveformReconstructionTool('Stage129RecCalo'))
acc.addEventAlgo(Inject('Stage144InjectActualEcalHits'))
acc.merge(CaloWaveformDigiCfg(flags, WaveformDigitisationTool=CompFactory.WaveformDigitisationTool('Stage122Calo')))
acc.addEventAlgo(Capture('Stage144CaptureActualEcalADC'))
import StoreGateBindings.Bindings
assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n')
for library in ['libIdentifier.so', 'libScintIdentifier.so', 'libScintReadoutGeometry.so',
                'libFaserCaloSimEvent.so', 'libCaloReadoutGeometry.so', 'libWaveRawEvent.so',
                'libScintSimEvent.so', 'libxAODFaserWaveform.so']:
    assert ROOT.gSystem.Load(library) >= 0, library
for header in ['stage138_response.hxx', 'stage129_rng.hxx', 'stage129_official.hxx', 'stage144_ecal.hxx']:
    assert ROOT.gInterpreter.Declare(Path('ml', header).read_text()), header
assert acc.run(1).isSuccess()

with np.load('ntuples/energy_ml_stage131/matched_input.npz') as data:
    selected = np.flatnonzero(data['frame_index'] == index)
    assert len(selected) <= 1
    status = data['calo_status'][selected[0]] if len(selected) else None
if status is not None:
    for wave in records['waves']:
        assert int(wave['result'][0]) == int(status[wave['channel']]), (index, wave['channel'], status, wave['result'])
assert ROOT.gInterpreter.Declare(Path('ml/stage141_analog.hxx').read_text())
waves = sorted(records['waves'], key=lambda row: row['id32'])
ids = records['all_geometry_PMTS']
n = len(waves[0]['adc']) if waves else 600
groups = {category: [] for category in [0, 1, 2]}
for row in records['source_timing']:
    groups[int(row[5])].extend([row[0], row[3], row[1]])
full = [value for row in records['source_timing'] for value in [row[0], row[3], row[1]]]
total = [list(row) for row in ROOT.Stage141Analog(full, records['conditions'], ids, seed, n)]
split = {category: [list(row) for row in ROOT.Stage141Analog(hits, records['conditions'], ids, seed, n)]
         for category, hits in groups.items()}
lookup = {row['id32']: row for row in waves}
mismatch, maximum = 0, 0.
for j, row in enumerate(total):
    if int(row[0]) in lookup:
        mismatch += int(int(row[5]) != lookup[int(row[0])]['adc'][int(row[1])])
    delta = abs(sum(split[category][j][2] for category in groups)-row[2])
    maximum = max(maximum, delta)
    assert delta <= 32*np.finfo('float32').eps*max(1., abs(row[2]))
assert mismatch == 0
charges = []
for wave in waves:
    # Use the actual reconstructed finite integration window, not a scintillator assumption.
    window = wave['result'][6:8]
    assert window[0] >= 0 and window[1] >= window[0]
    take = [j for j, row in enumerate(total) if int(row[0]) == wave['id32'] and window[0] <= 2*row[1] <= window[1]]
    convert = 2*2/16384/50*1000
    values = {category: convert*sum(split[category][j][2] for j in take) for category in groups}
    signal = convert*sum(total[j][2] for j in take)
    charges.append(dict(index=index, channel=wave['channel'], window_start_ns=window[0], window_end_ns=window[1],
                        total_analog_pC=signal, mu_root_pC=values[0], nonmu_root_pC=values[1], unknown_root_pC=values[2],
                        additivity_delta_pC=sum(values.values())-signal,
                        actual_signed_raw_pC=wave['result'][1], actual_fit_charge_pC=wave['result'][2], status=int(wave['result'][0])))
with (OUT/f'parent_{index}_charge.tsv').open('w') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(charges[0]), delimiter='\t', lineterminator='\n')
    writer.writeheader()
    writer.writerows(charges)
result = dict(passed=True, frame_index=index, ADC_samples=sum(len(row['adc']) for row in waves), ADC_mismatch=mismatch,
              clipped_samples=sum(value == 0 for row in waves for value in row['adc']),
              geometry_PMTS_including_uncabled=len(ids), actual_cabled_PMTS=len(waves),
              max_analog_sum_delta_ADC=maximum, max_window_sum_delta_pC=max(abs(row['additivity_delta_pC']) for row in charges),
              original_calo_status_exact=True if status is not None else None,
              original_selected_reference_available=status is not None,
              original_full_private_states_exact=True if original else None,
              original_Calo_raw_charge_reference='not retained; no original raw-charge equality claim',
              ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()), CPU_s=time.process_time()-cpu,
              wall_s=time.perf_counter()-tick, RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              new_G4=0, new_independent_nu=0, new_energy_fits=0, reserved_forward=0,
              scope='Ecal actual digital/source control, SD-corrected hits; not incident energy or data calibration; nonzero status gives no timing')
if STAGE != 144:
    result.update(mixed_finite_window_channels=[row['channel'] for row in charges if row['mu_root_pC'] > 0 and row['nonmu_root_pC'] > 0],
                  clipped_channels=[row['channel'] for row in waves if any(value == 0 for value in row['adc'])],
                  original_full_private_state_available=original is not None)
(OUT/f'parent_{index}_summary.json').write_text(json.dumps(result, indent=2)+'\n')
with gzip.open(CACHE/f"parent_{index}_{plan.get('ecal_control_name', 'control')}.json.gz", 'wt') as stream:
    json.dump(records, stream, separators=(',', ':'))
print(result, flush=True)
