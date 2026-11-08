"""Actual fixed-prefix Ecal HITS -> private digitizer -> ADC/raw, batch only."""
import csv
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
from EcalGeoModel.EcalGeoModelConfig import EcalGeometryCfg
from CaloDigiAlgs.CaloDigiAlgsConfig import CaloWaveformDigiCfg
from WaveformConditionsTools.WaveformDigitizationConfig import WaveformDigitizationCfg
from WaveformConditionsTools.WaveformCableMappingConfig import WaveformCableMappingCfg
from WaveformConditionsTools.WaveformTimingConfig import WaveformTimingCfg

OUT = Path('workbook/stage152_energy_ml')
CACHE = Path('ntuples/energy_ml_stage152')
phase = sys.argv[1]
count = 1 if phase == 'pilot' else 4
plan = json.loads((OUT/'protocol.json').read_text())
with gzip.open(plan['paired_reference'], 'rt') as stream:
    capsule = json.load(stream)
reference = json.loads(capsule['ntuples/energy_ml_stage151/full/paired.json.gz'])
seed_reference = json.loads(capsule['workbook/stage151_energy_ml/full/seeds.json'])
legacy = json.loads(capsule['ntuples/energy_ml_stage151/full/legacy.json.gz'])['records']
records, charges = [], []
cpu, tick = time.process_time(), time.perf_counter()


class Seed(PyAthena.Alg):
    def execute(self):
        store = PyAthena.py_svc('StoreGateSvc')
        event = store.retrieve('EventInfo', 'McEventInfo').event_ID()
        index = len(records)
        run, number = int(event.run_number()), int(event.event_number())
        ref = seed_reference['records'][index]
        assert (run, number) == (ref['run'], ref['event'])
        seed = 720000000+10000*number
        ROOT.Stage129PrivateSeed('Calo', seed)
        before = str(ROOT.Stage129PrivateState('Calo'))
        assert seed == ref['seeds']['Calo'] and before == ref['before']['Calo']
        records.append(dict(entry=index, run=run, event=number, seed=seed, before=before,
            lumiblock=int(event.lumi_block()), timestamp=int(event.time_stamp()),
            execute_entry_CPU_s=time.process_time()-cpu))
        return PyAthena.StatusCode.Success


class Capture(PyAthena.Alg):
    def execute(self):
        record = records[-1]
        index = record['entry']
        record['after'] = str(ROOT.Stage129PrivateState('Calo'))
        assert record['after'] == seed_reference['records'][index]['after']['Calo']
        store = PyAthena.py_svc('StoreGateSvc')
        waves = []
        for wave in store.retrieve('RawWaveformContainer', 'CaloWaveforms'):
            adc = [int(v) for v in wave.adc_counts()]
            channel, id32 = int(wave.channel()), int(wave.identify32().get_compact())
            result = list(ROOT.Stage129Official('Calo', channel, id32, adc))
            ref = next(v for v in reference[index]['readout'] if v['name'] == f'Calo{channel}')
            assert ref['present']
            assert int(result[0]) == ref['status']
            assert np.float32(result[1]) == np.float32(ref['raw_charge_pC'])
            waves.append(dict(channel=channel, id32=id32, adc=adc, status=int(result[0]),
                raw_charge_pC=result[1], baseline_mV=result[3], baseline_rms_mV=result[4],
                localtime_ns=result[5] if int(result[0]) == 0 else None, window_ns=result[6:8]))
        timing = [list(row) for row in ROOT.Stage144EcalTiming()]
        conditions = list(ROOT.Stage122Conditions('Calo'))
        ids = list(ROOT.Stage144EcalIdentifiers())
        # Inputs are actual persistent SD-corrected hits; never reapply Birks.
        flat = [value for row in timing for value in [row[0], row[3], row[1]]]
        analog = [list(row) for row in ROOT.Stage141Analog(flat, conditions, ids, record['seed'], 600)]
        support = [list(row) for row in ROOT.Stage152Support(timing, ids)]
        lookup = {row['id32']: row for row in waves}
        mismatch = sum(int(row[5]) != lookup[int(row[0])]['adc'][int(row[1])]
                       for row in analog if int(row[0]) in lookup)
        assert mismatch == 0
        conversion = 2*2000/16384/50
        channel_rows = []
        for wave in sorted(waves, key=lambda row: row['channel']):
            assert wave['window_ns'] == [780., 930.]
            channel = wave['channel']
            all_rows = [row for row in analog if int(row[0]) == wave['id32']]
            take = [row for row in all_rows if 780 <= 2*row[1] <= 930]
            finite = conversion*sum(row[2] for row in take)
            full = conversion*sum(row[2] for row in all_rows)
            signal_float = conversion*sum(row[3] for row in take)
            baseline_estimate_ADC = wave['baseline_mV']*16384/2000
            baseline_noise = conversion*sum(baseline_estimate_ADC-row[4] for row in take)
            rounding_clipping = conversion*sum(row[4]-row[3]-row[5] for row in take)
            independent_raw = 2/50*sum(float(np.float32(wave['baseline_mV']-2000/16384*wave['adc'][int(row[1])]))
                                      for row in take)
            delta = independent_raw-wave['raw_charge_pC']
            assert abs(delta) <= 2e-12*max(1, abs(wave['raw_charge_pC'])), delta
            decomposition_delta = signal_float+baseline_noise+rounding_clipping-wave['raw_charge_pC']
            assert abs(decomposition_delta) <= 2e-10*max(1, abs(wave['raw_charge_pC'])), decomposition_delta
            hit_rows = [row for row in timing if int(row[0]) == wave['id32']]
            support_row = next(row for row in support if int(row[0]) == wave['id32'])
            old = legacy[index]['readout'][f'Calo{channel}']
            channel_rows.append(dict(entry=index, run=record['run'], event=record['event'], channel=channel,
                hits_N=len(hit_rows), encoded_SD_energyLoss_MeV=sum(row[1] for row in hit_rows),
                histogram_excluded_hits_N=int(support_row[1]), histogram_excluded_energyLoss_MeV=support_row[2],
                corrected_time_min_ns=min((row[3] for row in hit_rows), default=None),
                corrected_time_max_ns=max((row[3] for row in hit_rows), default=None),
                finite_window_analog_pC=finite, full_acquisition_analog_pC=full,
                finite_over_full=finite/full if full > 0 else None,
                actual_signed_raw_pC=wave['raw_charge_pC'], status=wave['status'],
                float_signal_pC=signal_float, baseline_noise_pC=baseline_noise,
                rounding_clipping_pC=rounding_clipping, independent_raw_delta_pC=delta,
                decomposition_delta_pC=decomposition_delta,
                legacy_same_branch_raw_pC=old['raw_charge_pC'], legacy_same_branch_status=old['stored']['status'],
                clipped_samples=sum(value == 0 for value in wave['adc'])))
        charges.extend(channel_rows)
        record.update(waves=waves, source_timing=timing, conditions=conditions, geometry_PMT_identifiers=ids,
            histogram_support=support, ADC_samples=sum(len(wave['adc']) for wave in waves), ADC_mismatch=mismatch,
            source_HITS_rewritten=False, current_raw_status_exact=True, private_RNG_exact=True,
            execute_end_CPU_s=time.process_time()-cpu)
        print('CAPTURE', index, 'HITS', len(timing), 'ADC', record['ADC_samples'], flush=True)
        return PyAthena.StatusCode.Success


flags = initConfigFlags()
flags.Input.Files = [plan['input_HITS']]
flags.Input.isMC = True
flags.Input.ProjectName = 'mc20'
flags.IOVDb.DatabaseInstance = 'OFLP200'
flags.GeoModel.FaserVersion = 'FASERNU-04'
flags.IOVDb.GlobalTag = 'OFLCOND-FASER-04'
flags.Detector.GeometryEcal = True
flags.Concurrency.NumThreads = 0
flags.Exec.MaxEvents = count
flags.Exec.OutputLevel = 4
flags.lock()
acc = MainServicesCfg(flags)
acc.merge(PoolReadCfg(flags))
acc.merge(EcalGeometryCfg(flags))
acc.merge(WaveformDigitizationCfg(flags))
acc.merge(WaveformCableMappingCfg(flags))
acc.merge(WaveformTimingCfg(flags))
acc.addPublicTool(CompFactory.WaveformDigiConditionsTool('Stage122CondCalo', Detector='Calo'))
acc.addPublicTool(CompFactory.WaveformReconstructionTool('Stage129RecCalo'))
acc.addEventAlgo(Seed('Stage152OriginalEventAndPrivateSeed'))
acc.merge(CaloWaveformDigiCfg(flags, WaveformDigitisationTool=CompFactory.WaveformDigitisationTool('Stage122Calo')))
acc.addEventAlgo(Capture('Stage152ActualEcalResponse'))
import StoreGateBindings.Bindings
assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n')
for library in ['libIdentifier.so', 'libScintIdentifier.so', 'libScintReadoutGeometry.so',
                'libFaserCaloSimEvent.so', 'libCaloReadoutGeometry.so', 'libWaveRawEvent.so',
                'libScintSimEvent.so', 'libxAODFaserWaveform.so']:
    assert ROOT.gSystem.Load(library) >= 0, library
for header in ['stage138_response.hxx', 'stage129_rng.hxx', 'stage129_official.hxx',
               'stage144_ecal.hxx', 'stage141_analog.hxx', 'stage152_support.hxx']:
    assert ROOT.gInterpreter.Declare(Path('ml', header).read_text()), header
assert acc.run(count).isSuccess()
assert len(records) == count
with gzip.open(CACHE/f'{phase}.json.gz', 'wt') as stream:
    json.dump(dict(records=records, source_timing_columns=['id32', 'encoded_SD_energyLoss_MeV',
        'globaltime_ns', 'digitizer_corrected_time_ns', 'center_z_TOF_ns'],
        conditions_columns=['base_mean_ADC', 'base_rms_ADC', 'preshower_time_slope', 'cb_alpha', 'cb_n',
                            'cb_sigma_ns', 'cb_mean_ns', 'cb_norm'],
        conditions='OFLCOND-FASER-04', geometry='FASERNU-04'), stream, separators=(',', ':'), allow_nan=False)
with (OUT/f'{phase}_channels.tsv').open('w') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(charges[0]), delimiter='\t', lineterminator='\n')
    writer.writeheader()
    writer.writerows(charges)
summary = dict(passed=True, phase=phase, N=count, actual_ADC_samples=sum(r['ADC_samples'] for r in records),
    actual_ADC_mismatch=sum(r['ADC_mismatch'] for r in records),
    current_raw_status_identity_exact_N=count, private_initial_final_RNG_exact_N=count,
    actual_readout_views=len(charges), actual_geometry_PMTS=len(records[0]['geometry_PMT_identifiers']),
    CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
    event_CPU_s=[r['execute_end_CPU_s']-r['execute_entry_CPU_s'] for r in records],
    ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()), RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    result_bytes=(CACHE/f'{phase}.json.gz').stat().st_size, new_G4=0, fits=0, reserved_forward=0,
    same_surface_truth_pull=False, calibrated_gain=False, overall_complete=False)
assert summary['result_bytes'] <= plan['resources']['final_event_bytes_cap']
(OUT/f'{phase}_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(summary, flush=True)
