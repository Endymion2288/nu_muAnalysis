"""Independent scalar ADC/charge algebra and fixed-parent summaries, no ROOT."""
import csv
import gzip
import json
import math
import struct
from collections import defaultdict
from pathlib import Path
ROOT=Path.cwd();OUT=ROOT/'workbook/stage179_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage179'
p=json.loads((OUT/'protocol.json').read_text());checks=[];allrows=[];parents=[];corrections=[]
convert=2*2/16384/50*1000
def f32(v):return struct.unpack('f',struct.pack('f',v))[0]
for index in p['indices']:
    with gzip.open(CACHE/f'parent_{index}_response.json.gz','rt') as stream:response=json.load(stream)
    summary=json.loads((OUT/f'parent_{index}_summary.json').read_text());assert summary==response['summary'] and summary['passed']
    charge_rows=list(csv.DictReader((OUT/f'parent_{index}_charges.tsv').open(),delimiter='\t'))
    rowmap={(r['detector'],int(r['channel'])):r for r in charge_rows};adc_N=negative_N=0
    for detector,record in response['records'].items():
        if not record['waves']:continue
        analog=response['analog'][detector];total=analog['total'];split=analog['split']
        for j,row in enumerate(total):
            delta=abs(math.fsum(v[j] for v in split.values())-row[2])
            assert delta<=32*2**-23*max(1,abs(row[2]))
        for wave in record['waves']:
            a,b=wave['result'][6:8];pedestal=record['conditions'][0];fitted=wave['result'][3]/(2000/16384)
            positions=[j for j,r in enumerate(total) if int(r[0])==wave['id32']]
            window=[j for j in positions if a<=2*total[j][1]<=b]
            for j in positions:
                row=total[j];z=f32(row[4]-row[3]);unclip=math.floor(z+.5) if z>=0 else math.ceil(z-.5)
                assert max(0,unclip)==wave['adc'][int(row[1])]==int(row[5]);adc_N+=1
            actual_window=[f32(f32(wave['result'][3])-f32(f32(2000/16384)*f32(total[j][5]))) for j in window]
            manual=f32(2*sum(actual_window))/50
            assert f32(manual*50)==f32(wave['result'][1]*50)
            saved=rowmap[detector,wave['channel']]
            # Counterfactuals are rederived from retained actual analog samples, with C++ float subtraction.
            # Keep every original native TSV unchanged for exact failed/successful transport auditing.
            unlimited=[]
            for j in window:
                z=f32(total[j][4]-total[j][3])
                unlimited.append(math.floor(z+.5) if z>=0 else math.ceil(z-.5))
            updated=dict(no_clip_same_noise_pC=convert*math.fsum(fitted-u for u in unlimited),
                rounding_pC=convert*math.fsum(total[j][4]-total[j][3]-u for j,u in zip(window,unlimited)),
                clipping_pC=convert*math.fsum(u-total[j][5] for j,u in zip(window,unlimited)))
            changes={k:dict(original=float(saved[k]),corrected=v) for k,v in updated.items() if abs(float(saved[k])-v)>1e-9}
            if changes:corrections.append(dict(index=index,detector=detector,channel=wave['channel'],changes=changes))
            saved=dict(saved,**{k:str(v) for k,v in updated.items()})
            for category,values in split.items():
                value=convert*math.fsum(values[j] for j in window)
                assert abs(value-float(saved[category+'_pC']))<=1e-10*max(1,abs(value))
            ideal=convert*math.fsum(total[j][2] for j in window)
            assert abs(ideal-float(saved['signal_pC']))<=1e-10*max(1,abs(ideal))
            raw=float(saved['actual_signed_raw_pC']);negative_N+=raw<0
            parts=[float(saved[k]) for k in ['signal_pC','float_amplitude_pC','noise_pC','rounding_pC','clipping_pC','pedestal_error_pC','raw_float_storage_delta_pC']]
            assert abs(math.fsum(parts)-raw)<=1e-8*max(1,abs(raw))
            assert abs(float(saved['no_clip_same_noise_pC'])-(raw-float(saved['raw_float_storage_delta_pC'])-float(saved['clipping_pC'])))<=1e-8*max(1,abs(raw))
            allrows.append({k:(v if k=='detector' else int(v) if k in ['index','channel','status'] else float(v)) for k,v in saved.items()})
    assert adc_N==summary['ADC_samples'] and summary['ADC_mismatch']==0
    checks.append(dict(index=index,passed=True,ADC_scalar_samples=adc_N,channels_N=len(charge_rows),negative_signed_raw_N=negative_N))
    parents.append(dict(index=index,original_selected_reference_available=summary['original_selected_reference_available'],
        ADC_samples=adc_N,clipped_samples=summary['clipped_samples'],negative_signed_raw_N=negative_N,
        **(summary['diagnostic'] or dict(truth_E_GeV=None,pz0_GeV=None,direct_cal_relative_error=None,traditional_relative_error=None))))
groups=defaultdict(list)
for row in allrows:groups[row['detector']].append(row)
stats=[]
for detector,rows in groups.items():
    stats.append(dict(detector=detector,channels_N=len(rows),status0_N=sum(r['status']==0 for r in rows),
        positive_ideal_N=sum(r['signal_pC']>0 for r in rows),negative_raw_N=sum(r['actual_signed_raw_pC']<0 for r in rows),
        clipping_nonzero_channels_N=sum(r['clipping_pC']!=0 for r in rows),
        sum_abs_raw_minus_ideal_pC=math.fsum(abs(r['actual_signed_raw_pC']-r['signal_pC']) for r in rows),
        sum_abs_unclipped_minus_ideal_pC=math.fsum(abs(r['no_clip_same_noise_pC']-r['signal_pC']) for r in rows),
        sum_abs_noise_plus_pedestal_pC=math.fsum(abs(r['noise_pC']+r['pedestal_error_pC']) for r in rows),
        sum_abs_clipping_pC=math.fsum(abs(r['clipping_pC']) for r in rows),
        sum_signal_pC=math.fsum(r['signal_pC'] for r in rows),
        sum_before_S0_pC=math.fsum(r['before_S0_pC'] for r in rows),sum_after_S0_pC=math.fsum(r['after_S0_pC'] for r in rows),
        sum_unknown_S0_pC=math.fsum(r['unknown_S0_pC'] for r in rows)))
for name,rows in [('charge_interventions.tsv',allrows),('parent_diagnostics.tsv',parents),('response_summary.tsv',stats)]:
    with (OUT/name).open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n',quoting=csv.QUOTE_NONNUMERIC);writer.writeheader();writer.writerows(rows)
r=dict(passed=True,parents_N=len(parents),original_selected_N=sum(r['original_selected_reference_available'] for r in parents),
    ADC_samples=sum(r['ADC_scalar_samples'] for r in checks),channels_N=len(allrows),ADC_mismatch=0,
    negative_signed_raw_N=sum(r['negative_signed_raw_N'] for r in checks),clipped_samples=sum(r['clipped_samples'] for r in parents),
    manual_raw_exact=True,source_additivity_and_scalar_charge=True,parent50_private_states_exact=True,
    old_calo_raw_reference_available=False,summary=stats,counterfactual_float_subtraction_corrected=True,
    counterfactual_corrected_channels_N=len(corrections),energy_fits=0,new_forward=0,new_G4=0,
    overall_complete=False,scope='Original conditional12 train controls; no detector-wide error calibration, energy improvement, population proportion or independent validation.')
(OUT/'independent_validation.json').write_text(json.dumps(dict(passed=True,parents=checks),indent=2)+'\n')
(OUT/'counterfactual_arithmetic_correction.json').write_text(json.dumps(dict(passed=True,
    cause='Pinned baseline-amplitude is float subtraction before std::round; native Python initial counterfactual promoted subtraction to double. Actual Stage141Analog/ADC/raw/source signals unaffected.',
    no_new_transport_or_reconstruction=True,original_per_parent_TSV_unchanged=True,final_table='charge_interventions.tsv',corrected_channels=corrections),indent=2)+'\n')
(OUT/'physical_summary.json').write_text(json.dumps(r,indent=2)+'\n');print(r,flush=True)
