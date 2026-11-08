"""Condor-only safe persistent-v1 readout, no converter or fitted charge."""
import gzip
import json
import math
import resource
import sys
import time
from pathlib import Path
import ROOT

OUT=Path('workbook/stage162_energy_ml');CACHE=Path('ntuples/energy_ml_stage162')
phase=sys.argv[1];assert phase in ['pilot','full','repeat']
count=64 if phase=='full' else 4
manifest=json.loads((OUT/'matched_manifest.json').read_text())
parents=manifest['records'][:count];assert all(r['unique_pair'] for r in parents)
cpu,tick=time.process_time(),time.perf_counter()
for library in ['libGaudiKernel.so','libAthenaKernel.so','libAthContainers.so','libxAODCore.so',
                'libxAODFaserWaveform.so','libxAODFaserWaveformDict.so']:
    assert ROOT.gSystem.Load(library)>=0,library
ROOT.gInterpreter.AddIncludePath(str(Path('ml').resolve()))
assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n'+Path('ml/stage162_readout.hxx').read_text())
reader=ROOT.Stage162.Reader(manifest['REC']);records=[];cost=[]
def finite(value):return float(value) if math.isfinite(float(value)) else None
for parent in parents:
    start=time.process_time();waves=[]
    for w in reader.read(parent['native_entry']):
        waves.append(dict(detector=str(w.detector),channel=int(w.channel),id32=int(w.id32),status=int(w.status),
            secondary=bool(w.secondary),raw_charge_pC=finite(w.rawCharge),raw_peak_mV=finite(w.rawPeak),
            baseline_mV=finite(w.baseline),baseline_rms_mV=finite(w.rms),
            localtime_ns=finite(w.localtime) if w.status==0 else None,wave_sample_N=int(w.waveN),time_sample_N=int(w.timeN),sample_sum_mV=finite(w.sampleSum),sample_abs_sum_mV=finite(w.absSum),
            finite_sample_N=int(w.finiteN),sample_max_mV=finite(w.sampleMax),
            time_start_ns=finite(w.timeStart) if w.status==0 else None,time_end_ns=finite(w.timeEnd) if w.status==0 else None,
            time_spacing_2ns=bool(w.spacing2) if w.status==0 else None))
    records.append(dict(PHYS_entry=parent['PHYS_entry'],native_entry=parent['native_entry'],
        run=parent['run'],event=parent['event'],waves=waves))
    cost.append(time.process_time()-start)
with gzip.open(CACHE/f'{phase}_raw.json.gz','wt') as stream:json.dump(records,stream,separators=(',',':'),allow_nan=False)
summary=dict(passed=True,N=len(records),containers=[str(v) for v in reader.containers()],CPU_s=time.process_time()-cpu,
    wall_s=time.perf_counter()-tick,ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),
    RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,first_read_CPU_s=cost[0],
    post_first_read_CPU_s=sum(cost[1:]),post_first_read_mean_CPU_s=sum(cost[1:])/len(cost[1:]),
    waveform_units='Stored waveform mV and time ns by v1 EDM; no digitizer ADC-code or calibration certification',
    scope='Transient stored-window amplitude sum/max only; status0-only time-vector QA; no sample arrays retained')
(OUT/f'{phase}_raw_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary,flush=True)
