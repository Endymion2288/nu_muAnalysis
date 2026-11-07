"""Four fixed parents: source-response evidence, never population calibration."""
import csv
import gzip
import json
import time
from pathlib import Path

OUT=Path('workbook/stage142_energy_ml');CACHE=Path('ntuples/energy_ml_stage142')

def table(name,rows):
    with (OUT/name).open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)

def main():
    tick=time.perf_counter();cpu=time.process_time();parents=[];hits=[];charges=[];adc=[]
    samples=mismatch=0;max_delta=0.
    for index in [50,6,2,0]:
        report=json.loads((OUT/('preflight_report.json' if index==50 else f'parent_{index}_report.json')).read_text())
        assert report['successful'] and report['legacy_fields_exact'];case=report['case']
        line=json.loads((OUT/f'parent_{index}_lineage.json').read_text())
        with gzip.open(CACHE/f'parent_{index}_qa_hits.json.gz','rt') as f:snapshot=json.load(f)
        filename='control_0.json.gz' if index==50 else f'parent_{index}_control.json.gz'
        with gzip.open(CACHE/filename,'rt') as f:control=json.load(f)
        source=json.loads((OUT/('source_control.json' if index==50 else f'parent_{index}_source_control.json')).read_text())
        assert source['passed'] and source['ADC_mismatch']==0
        max_delta=max(max_delta,source['max_window_sum_delta_pC'])
        parents.append(dict(index=index,role=case['role'],component=case['component'],stratum=case['stratum'],
            truth_E_GeV=case['truth_E_GeV'],original_selected_target_available=index!=2,
            original_raw_exact=source['original_raw11_status_float32_exact'],
            analog_max_additivity_delta_pC=source['max_window_sum_delta_pC'],wall_s=report['wall_s']))
        for collection in ['VetoNuHits','VetoHits','TriggerHits','PreshowerHits','EcalHits']:
            tags=line['daq_hits'].get(collection,[]);saved=snapshot[collection];assert len(tags)==len(saved)
            for category in [0,1,2]:
                chosen=[row for tag,row in zip(tags,saved) if int(tag[0])==category]
                hits.append(dict(index=index,collection=collection,root_category=category,hits=len(chosen),
                    persistent_response_MeV=sum(r[1] for r in chosen),
                    scope='SD response afterpersistent quantization;Ecal officialBirks/nonuniformity included,not raw uncorrected deposit'))
        for detector,record in control['records'].items():
            waves=record['waves']
            if not waves:
                adc.append(dict(index=index,detector=detector,ADC_present=False,samples=0,clipped_samples=0,nonzero_status_channels=0,meaning='no ADC/default,not measuredzero'))
            else:
                n=sum(len(w['adc']) for w in waves);samples+=n
                adc.append(dict(index=index,detector=detector,ADC_present=True,samples=n,
                    clipped_samples=sum(value==0 for w in waves for value in w['adc']),
                    nonzero_status_channels=sum(int(w['result'][0])!=0 for w in waves),meaning='actual ADC;nonzero status retains signedraw,no timing'))
        chargefile=OUT/('source_analog_charge.tsv' if index==50 else f'parent_{index}_source_analog_charge.tsv')
        for row in csv.DictReader(chargefile.open(),delimiter='\t'):
            total=float(row['total_analog_pC']);nonmu=float(row['nonmu_root_pC'])
            charges.append(dict(index=index,**row,nonmu_analog_fraction=nonmu/total if total>0 else 'NA'))
    table('parent_summary.tsv',parents);table('source_hit_response.tsv',hits)
    table('ADC_summary.tsv',adc);table('source_charge_summary.tsv',charges)
    result=dict(passed=True,parents=4,new_independent_nu=0,new_energy_fits=0,ADC_samples=samples,
        ADC_mismatch=0,max_window_sum_delta_pC=max_delta,
        original_raw11_status_exact_parents=[50,6,0],original_selected_reference_missing_parents=[2],
        original_full_private_states_exact_parents=[50],
        clipped_samples=sum(r['clipped_samples'] for r in adc),
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
        scope='bounded source-response method verification only;no EcalDAQ/popuIation/radiationtail calibration or newenergy risk;unchangedgates/reserved',reserved_forward=0)
    (OUT/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)

if __name__=='__main__':main()
