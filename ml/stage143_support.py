"""Fixed role1 support for the one channel not covered by four controls."""
import csv
import gzip
import json
import resource
import time
from pathlib import Path

OUT=Path('workbook/stage143_energy_ml')

def main():
    tick=time.perf_counter();cpu=time.process_time()
    with gzip.open('ntuples/energy_ml_stage131/production_cases.json.gz','rt') as f:cases=json.load(f)
    with gzip.open('ntuples/energy_ml_stage137/boundary_evidence.json.gz','rt') as f:evidence=json.load(f)
    counts={};eligible=[]
    for case in cases:
        if case['role']!=1:continue
        record=evidence[str(case['frame_index'])]['report']
        matching=[v for k,v in record['lineage']['deposits'].items() if 'vetonu' in k.lower()]
        energy=sum(sum(v['all_MeV']) for v in matching)
        selected=record['original_selected_N'];key=(case['stratum'],case['component'],selected)
        row=counts.setdefault(key,dict(stratum=key[0],component=key[1],original_selected=selected,parents=0,positive_VetoNu=0))
        row['parents']+=1;row['positive_VetoNu']+=int(energy>0)
        if energy>0:eligible.append(dict(frame_index=case['frame_index'],case=case,original_selected=selected,VetoNu_response_MeV=energy))
    eligible.sort(key=lambda r:r['frame_index']);chosen=eligible[:2]
    with (OUT/'support.tsv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(next(iter(counts.values()))),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(counts.values())
    result=dict(train_parents=sum(r['parents'] for r in counts.values()),positive_VetoNu=len(eligible),
        selected_indices=[r['frame_index'] for r in chosen],selected_controls=chosen,
        scope='role1 only;first atmost2originalframepositivecontrols;no risk/sourcefraction choice;not populationresponse/energy improvement',
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        no_new_G4=True,no_new_model_fit=True,reserved_forward=0)
    (OUT/'support.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)

if __name__=='__main__':main()
