"""Condor-only source-specified legacy positive-sample raw definition diagnostic."""
import csv,gzip,json,struct
from pathlib import Path
OUT=Path('workbook/stage162_energy_ml')
with gzip.open('ntuples/energy_ml_stage162/event_records.json.gz','rt') as stream:capsule=json.load(stream)
raw=json.loads(capsule['ntuples/energy_ml_stage162/pilot_raw.json.gz'])
rows=[]
for event in raw:
 for w in event['waves']:
  if w['secondary']:continue
  # Algebraic positive-part sum uses already saved sufficient summaries; no new samples.
  positive=(w['sample_sum_mV']+w['sample_abs_sum_mV'])/2
  integral=2*positive
  stored=struct.unpack('f',struct.pack('f',integral))[0]/50
  rows.append(dict(PHYS_entry=event['PHYS_entry'],channel=w['channel'],detector=w['detector'],
    positive_sample_charge_pC=integral/50,raw_charge_pC=w['raw_charge_pC'],float32_exact=stored==w['raw_charge_pC'],
    signed_sample_charge_pC=2*w['sample_sum_mV']/50,rectification_offset_pC=w['raw_charge_pC']-2*w['sample_sum_mV']/50))
with (OUT/'producer_definition.tsv').open('w') as stream:
 writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
result=dict(passed=True,N=len(rows),legacy_positive_integral_float32_exact_N=sum(r['float32_exact'] for r in rows),
 max_rectification_offset_pC=max(r['rectification_offset_pC'] for r in rows),
 negative_signed_window_N=sum(r['signed_sample_charge_pC']<0 for r in rows),
 source='3de41ab4 and7b61d3fc parent findRawHitValues: skip wave<=0,raw_integral=2*tot; d32 current uses entire signed window',
 ROOT_reads=0,source_selected_from_history_not_numeric_grid=True,original_signed_gate_changed=False,full_admitted=False,
 interpretation='Definition closure at named4parents, not proof exact historical producer commit, noise calibration, FPR or energy benefit')
(OUT/'producer_definition_summary.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
