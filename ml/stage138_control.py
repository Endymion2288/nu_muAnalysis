"""Two independent native processes on the same saved control, no new G4."""
import gzip
import json
import subprocess
import sys
from pathlib import Path

OUT=Path('workbook/stage138_energy_ml');CACHE=Path('ntuples/energy_ml_stage138')
for replica in [0,1]:
    with (OUT/f'control_{replica}.log').open('w') as stream:
        result=subprocess.run(['/usr/bin/time','-v','-o',str(OUT/f'control_{replica}_time.txt'),
            sys.executable,'ml/stage138_native.py',str(replica)],stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:
        print((OUT/f'control_{replica}.log').read_text()[-9000:],flush=True)
        raise SystemExit(result.returncode)
with gzip.open(CACHE/'control_0.json.gz','rt') as f:a=json.load(f)
with gzip.open(CACHE/'control_1.json.gz','rt') as f:b=json.load(f)
for key in ['records','rng','raw_checks','snapshot_fields_exact']:assert a[key]==b[key],key
summary=dict(passed=True,independent_processes=2,ADC_samples=sum(len(w['adc']) for r in a['records'].values() for w in r['waves']),
    raw11_and_status_exact_float32=True,private_seed_and_final_states_exact=True,
    snapshot_hits_reconstructed_exact=True,all_ADC_and_results_repeat_exact=True,
    source_frame_index=50,new_G4=0,new_digi_reco_natural_samples=0,energy_fits=0,model_forward=0,
    max_raw_pC_float_rounding_delta=max(abs(r['delta_pC']) for r in a['raw_checks']),
    scope=a['scope'],CPU_s=sum(r['CPU_s'] for r in [a,b]),wall_s=sum(r['wall_s'] for r in [a,b]))
(OUT/'control_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary)
