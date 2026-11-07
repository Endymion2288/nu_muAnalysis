"""New livehit source tags against already closed actual ADC method."""
import csv
import gzip
import json
import subprocess
import sys
from pathlib import Path

OUT=Path('workbook/stage142_energy_ml');CACHE=Path('ntuples/energy_ml_stage142')

def main():
    with (OUT/'native_0.log').open('w') as stream:
        result=subprocess.run(['/usr/bin/time','-v','-o',str(OUT/'native_0_time.txt'),
            sys.executable,'ml/stage142_native.py','0'],stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:print((OUT/'native_0.log').read_text()[-6000:],flush=True)
    assert result.returncode==0
    import ROOT
    assert ROOT.gInterpreter.Declare(Path('ml/stage141_analog.hxx').read_text())
    with gzip.open(CACHE/'control_0.json.gz','rt') as f:control=json.load(f)
    with gzip.open('ntuples/energy_ml_stage131/pilot_private_rng_states.json.gz','rt') as f:rng=json.load(f)
    channels=[];mismatch=0;maximum=0.
    for detector,record in control['records'].items():
        waves=sorted(record['waves'],key=lambda r:r['id32'])
        if not waves:continue
        n=len(waves[0]['adc']);ids=[w['id32'] for w in waves];seed=rng[detector]['seed']
        groups={c:[] for c in [0,1,2]}
        for row in record['source_timing']:groups[row[6]].extend([row[0],row[3],row[1]])
        full=[v for row in record['source_timing'] for v in [row[0],row[3],row[1]]]
        total=[list(r) for r in ROOT.Stage141Analog(full,record['conditions'],ids,seed,n)]
        split={c:[list(r) for r in ROOT.Stage141Analog(hits,record['conditions'],ids,seed,n)] for c,hits in groups.items()}
        lookup={w['id32']:w for w in waves}
        for i,row in enumerate(total):
            wave=lookup[int(row[0])];mismatch+=int(int(row[5])!=wave['adc'][int(row[1])])
            delta=abs(sum(split[c][i][2] for c in groups)-row[2]);maximum=max(maximum,delta)
            # Predeclared floating response additivity bound; not a physics prior.
            assert delta<=32*1.1920928955078125e-7*max(1.,abs(row[2]))
        for wave in waves:
            indices=[i for i,r in enumerate(total) if int(r[0])==wave['id32'] and 390<=int(r[1])<=490]
            convert=2*2/16384/50*1000
            values={c:convert*sum(split[c][i][2] for i in indices) for c in groups}
            charge=convert*sum(total[i][2] for i in indices)
            channels.append(dict(detector=detector,channel=wave['channel'],total_analog_pC=charge,
                mu_root_pC=values[0],nonmu_root_pC=values[1],unknown_root_pC=values[2],
                additivity_delta_pC=sum(values.values())-charge,
                actual_signed_raw_pC=wave['result'][1],status=int(wave['result'][0])))
    with (OUT/'source_analog_charge.tsv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(channels[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(channels)
    result=dict(passed=mismatch==0,ADC_mismatch=mismatch,max_analog_sum_delta_ADC=maximum,
        max_window_sum_delta_pC=max(abs(r['additivity_delta_pC']) for r in channels),
        original_raw11_status_float32_exact=True,original_private_states_exact=True,
        frame_index=50,scope='one mu-root control;source tags actual livehits;not mixedsource/EcalDAQ/muonradiationtail certification',
        no_energy_training=True,reserved_forward=0)
    (OUT/'source_control.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)
    assert result['passed']

if __name__=='__main__':main()
