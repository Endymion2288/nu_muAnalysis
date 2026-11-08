"""Actual persistent-v1 read, with sample/time access restricted before extraction."""
import resource
resource.setrlimit(resource.RLIMIT_CPU,(120,120))
import gzip
import json
import math
import sys
import time
from pathlib import Path
import ROOT

OUT=Path('workbook/stage196_energy_ml');CACHE=Path('ntuples/energy_ml_stage196')
phase=sys.argv[1];assert phase in ['pilot','full','audit']
p=json.loads((OUT/'protocol.json').read_text())
manifest=json.loads(Path(p['data_manifest']).read_text())
parents=manifest['records'][:4 if phase=='pilot' else 64]
cpu,tick=time.process_time(),time.perf_counter()
for library in ['libGaudiKernel.so','libAthenaKernel.so','libAthContainers.so','libxAODCore.so',
                'libxAODFaserWaveform.so','libxAODFaserWaveformDict.so']:
    assert ROOT.gSystem.Load(library)>=0,library
assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n'+Path('ml/stage196_readout.hxx').read_text())
reader=ROOT.Stage196.Reader(manifest['REC'])
records=[];cost=[]
def finite(v):return float(v) if math.isfinite(float(v)) else None
for parent in parents:
    assert parent['unique_pair']
    start=time.process_time();waves=[]
    for w in reader.read(parent['native_entry']):
        eligible=w.status==0 and not w.secondary and str(w.detector)!='CaloNu'
        wave=dict(detector=str(w.detector),channel=int(w.channel),id32=int(w.id32),status=int(w.status),
            secondary=bool(w.secondary),raw_charge_pC=finite(w.rawCharge),raw_peak_mV=finite(w.rawPeak),
            baseline_mV=finite(w.baseline),baseline_rms_mV=finite(w.rms),wave_sample_N=int(w.waveN),time_sample_N=int(w.timeN),
            localtime_ns=finite(w.localtime) if eligible else None,
            sample_sum_mV=finite(w.sampleSum),sample_abs_sum_mV=finite(w.absSum),sample_max_mV=finite(w.sampleMax),finite_sample_N=int(w.finiteN),
            samples_mV=[finite(v) for v in w.samples] if eligible else None,
            times_ns=[finite(v) for v in w.times] if eligible else None)
        assert eligible or (wave['samples_mV'] is None and wave['times_ns'] is None and wave['localtime_ns'] is None)
        waves.append(wave)
    records.append({**{k:parent[k] for k in ['PHYS_entry','native_entry','run','event']},'waves':waves})
    cost.append(time.process_time()-start)
with gzip.open(CACHE/f'{phase}_raw.json.gz','wt',compresslevel=1) as f:json.dump(records,f,separators=(',',':'),allow_nan=False)
summary=dict(passed=True,N=len(records),CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
    event_CPU_s=cost,ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    containers=[str(v) for v in reader.containers()],native_geometry_initialized=False,original_status_not_changed=True)
(OUT/f'{phase}_raw_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(summary,flush=True)
