"""Condor-only cached amplitude audit after pinned helper rejects old dictionary."""
import csv
import gzip
import json
import math
import struct
from collections import Counter,defaultdict
from pathlib import Path
OUT=Path('workbook/stage162_energy_ml');CACHE=Path('ntuples/energy_ml_stage162')
with gzip.open(CACHE/'pilot_raw.json.gz','rt') as stream:raw=json.load(stream)
with gzip.open('ntuples/energy_ml_stage161/event_records.json.gz','rt') as stream:capsule=json.load(stream)
old=json.loads(capsule['ntuples/energy_ml_stage161/pilot_raw.json.gz'])
rows=[];groups=defaultdict(Counter)
for prior,current in zip(old,raw):
    assert all(current[k]==v for k,v in prior.items() if k!='waves')
    assert len(prior['waves'])==len(current['waves'])
    for p,w in zip(prior['waves'],current['waves']):
        assert all(w[k]==v for k,v in p.items())
        if w['secondary']:continue
        size=w['wave_sample_N'];finite=size>0 and size==w['finite_sample_N']
        integral=w['raw_charge_pC']*50
        bits=struct.unpack('I',struct.pack('f',abs(integral)))[0]
        f=lambda i:struct.unpack('f',struct.pack('I',i))[0]
        ulp=max(f(bits+1)-f(bits),f(bits)-f(max(0,bits-1)))
        gamma=(size+2)*2**-53/(1-(size+2)*2**-53)
        bound=ulp/100+gamma*w['sample_abs_sum_mV']*2/50
        q=w['sample_sum_mV']*2/50;delta=abs(q-w['raw_charge_pC'])
        closed=finite and delta<=bound and w['sample_max_mV']==w['raw_peak_mV']
        assert w['status']==0 or all(w[k] is None for k in ['time_start_ns','time_end_ns','time_spacing_2ns'])
        row=dict(PHYS_entry=current['PHYS_entry'],event=current['event'],channel=w['channel'],detector=w['detector'],
            status=w['status'],samples=size,finite_samples=w['finite_sample_N'],sample_charge_pC=q,raw_charge_pC=w['raw_charge_pC'],
            delta_pC=delta,bound_pC=bound,closed=closed,raw_peak_exact=w['sample_max_mV']==w['raw_peak_mV'],
            status0_start_ns=w['time_start_ns'],status0_end_ns=w['time_end_ns'],status0_spacing2=w['time_spacing_2ns'])
        rows.append(row);g=groups[w['detector']];g['N']+=1;g['closed_N']+=closed;g['nonzero_status_N']+=w['status']!=0
with (OUT/'pilot_window_content.tsv').open('w') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n',quoting=csv.QUOTE_NONNUMERIC);writer.writeheader();writer.writerows(rows)
summary=dict(passed=True,terminal_experiment=True,admitted=False,N=len(raw),Stage161_raw_controls_exact=True,
    window_content=dict(N=len(rows),closed_N=sum(r['closed'] for r in rows),max_delta_pC=max(r['delta_pC'] for r in rows),
        max_bound_pC=max(r['bound_pC'] for r in rows),sample_counts=sorted({r['samples'] for r in rows}),
        raw_peak_exact_N=sum(r['raw_peak_exact'] for r in rows),finite_sample_N=sum(r['finite_samples'] for r in rows),
        nonzero_status_N=sum(r['status']!=0 for r in rows),status0_spacing2_N=sum(r['status0_spacing2'] is True for r in rows),
        status0_window_endpoints_ns=sorted({(r['status0_start_ns'],r['status0_end_ns']) for r in rows if r['status']==0}),
        by_detector={k:dict(v) for k,v in groups.items()}),
    native_events=0,dictionary_runtime='failed initialization: pinned FaserDetectorID requires VetoGm/Muon labels absent in frozen old dictionary',
    physical_ID_closure='unmeasured in old helper; Stage161 mismatch retained',
    waveform_scope='Stored reconstruction windows only by source; no full acquisition or raw ADC certification',
    ROOT_reads_this_audit=0,new_G4=0,energy_fits=0,promotion=False,overall_complete=False)
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
(OUT/'admission.json').write_text(json.dumps(dict(admitted=False,reason=summary['dictionary_runtime'],budget_relaxed=False),indent=2)+'\n')
print(summary)
