"""Batch-only numerical certification against the unchanged Stage179 response."""
import csv
import gzip
import json
import time
from pathlib import Path
import numpy as np
import ROOT

OUT=Path('workbook/stage184_energy_ml')

def main():
    assert ROOT.gInterpreter.Declare(Path('ml/stage184_window.hxx').read_text())
    p=json.loads((OUT/'protocol.json').read_text());rows=[]
    authoritative=list(csv.DictReader(open('workbook/stage179_energy_ml/charge_interventions.tsv'),delimiter='\t'))
    for index in p['reference_indices']:
        with gzip.open(f'ntuples/energy_ml_stage179/parent_{index}_response.json.gz','rt') as stream:r=json.load(stream)
        for detector,record in r['records'].items():
            window=(390,465) if detector=='Calo' else (390,490)
            tick=time.process_time();integrator=ROOT.Stage184Window(record['conditions'],*window)
            full=[v for h in record['source_timing'] for v in [h[0],h[3],h[1]]]
            values={int(x[0]):float(x[1]) for x in integrator.integrate(full,record['all_geometry_PMTS'])}
            elapsed=time.process_time()-tick
            for wave in record['waves']:
                original=next(q for q in authoritative if int(q['index'])==index and q['detector']==detector and int(q['channel'])==wave['channel'])
                actual=float(original['ideal_no_noise_no_clip_no_quantization_pC']);fast=values[wave['id32']]
                tolerance=32*np.finfo('float32').eps*max(1,abs(actual))
                assert abs(fast-actual)<=tolerance,(index,detector,wave['channel'],actual,fast,tolerance)
                rows.append(dict(index=index,detector=detector,channel=wave['channel'],reference_pC=actual,
                    fast_pC=fast,abs_delta_pC=abs(fast-actual),tolerance_pC=float(tolerance),detector_CPU_s=elapsed))
    with (OUT/'reference_closure.tsv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)
    result=dict(passed=True,parents_N=len(p['reference_indices']),channels_N=len(rows),max_abs_delta_pC=max(r['abs_delta_pC'] for r in rows),
        max_tolerance_fraction=max(r['abs_delta_pC']/r['tolerance_pC'] for r in rows),not_bit_exact=True)
    (OUT/'reference_summary.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)

if __name__=='__main__':main()
