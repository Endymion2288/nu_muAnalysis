"""Independent finite-window ADC integral and timing description, batch only."""
import csv
import gzip
import json
import math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path('workbook/stage138_energy_ml');CACHE=Path('ntuples/energy_ml_stage138')

def table(name,rows):
    with (OUT/name).open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n')
        writer.writeheader()
        writer.writerows({k:('NA' if r.get(k) is None or r.get(k)=='' else r[k])
                          for k in writer.fieldnames} for r in rows)

def main():
    with gzip.open(CACHE/'control_0.json.gz','rt') as stream:d=json.load(stream)
    raw=[];timing=[];fig,axes=plt.subplots(3,1,figsize=(9,8),layout='constrained')
    for detector,record in d['records'].items():
        rows=record['timing'];energy=sum(r[1] for r in rows)
        timing.append(dict(detector=detector,PMT_hit_contributions=len(rows),
            energy_MeV=energy,global0_1000_energy_MeV=sum(r[1] for r in rows if 0<=r[2]<1000),
            global_negative_energy_MeV=sum(r[1] for r in rows if r[2]<0),
            corrected_hist_underflow_energy_MeV=sum(r[1] for r in rows if r[3]<-20),
            min_global_ns=min((r[2] for r in rows),default=None),max_global_ns=max((r[2] for r in rows),default=None),
            min_corrected_ns=min((r[3] for r in rows),default=None),max_corrected_ns=max((r[3] for r in rows),default=None),
            scope='Trigger duplicates one hit into2PMTs;corrected hit time is before CBconvolution,not arrival-time measurement'))
        for wave in record['waves']:
            ch=wave['channel'];result=wave['result'];adc=np.array(wave['adc'],dtype=np.float32)
            if ch not in [4,5,14,6,7,8,9,10,11,12,13]:continue
            assert result[6:8]==[780.,980.]
            gain=np.float32(2./16.384);baseline=np.float32(result[3])
            signal=(baseline-(gain*adc).astype(np.float32)).astype(np.float32)
            reconstructed=float(np.float32(2*math.fsum(map(float,signal[390:491]))))/50
            delta=reconstructed-result[1]
            # Explicit float32 arithmetic bound for101 baseline-subtracted samples.
            bound=101*2/50*8*np.finfo(np.float32).eps*max(1.,abs(float(baseline)))
            assert abs(delta)<=bound,(detector,ch,delta,bound)
            raw.append(dict(detector=detector,channel=ch,status=int(result[0]),
                ADC_samples=len(adc),raw_window_samples=101,window_start_ns=780,window_end_ns=980,
                raw_pC=result[1],independent_ADC_raw_pC=reconstructed,delta_pC=delta,
                float32_arithmetic_bound_pC=bound,baseline_mV=float(baseline),
                nonzero_status_arrival_time_used=False))
            if ch in [14,8,12]:
                ax=axes[[14,8,12].index(ch)]
                ax.plot(np.arange(600)*2,signal,lw=.8)
                ax.axvspan(780,980,alpha=.15,color='orange')
                ax.set(title=f'{detector} channel {ch}; raw={result[1]:.6g} pC; status={int(result[0])}',
                       ylabel='Baseline minus ADC (mV)',xlim=(720,1040))
                ax.grid(alpha=.2)
    axes[-1].set_xlabel('Digitizer sample time (ns); not reconstructed hit arrival time')
    fig.savefig(OUT/'DAQ_control_waveforms.png',dpi=150);plt.close(fig)
    table('timing_control.tsv',timing);table('ADC_integral_validation.tsv',raw)
    table('raw11_control.tsv',[{k:v for k,v in r.items() if k not in ['window_ns']} for r in d['raw_checks']])
    (OUT/'independent_integral_validation.json').write_text(json.dumps(dict(passed=True,channels=len(raw),
        max_abs_delta_pC=max(abs(r['delta_pC']) for r in raw),
        actual_raw_window='780–980ns inclusive,101samples',
        scope='ADC rectangle integral and float32 arithmetic only; no analogue source decomposition or general timing calibration'),indent=2)+'\n')

if __name__=='__main__':main()
