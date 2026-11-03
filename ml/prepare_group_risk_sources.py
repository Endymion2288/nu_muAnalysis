#!/usr/bin/env python3
"""Bounded stage68 supplement: one listing of each known run, no event or ROOT reads."""
import csv,json,re,time,resource
from pathlib import Path
from collections import Counter
from group_risk import OUT,REPO,begin,resources,save
from report_expert_combination import table


def main():
    start=begin();manifest=list(csv.DictReader((REPO/'ml/configs/low_energy_files.tsv').open(),delimiter='\t'))
    roles={g:sorted(set(r['partition'] for r in manifest if r['group']==g)) for g in set(r['group'] for r in manifest)}
    historical={}
    for r in csv.DictReader((REPO/'ml/configs/files.tsv').open(),delimiter='\t'):
        name=r['input_rdo'] or r['input'];match=re.search(r'-(\d{5}-\d{5})-s0014',name)
        component='charm' if 'charm' in name else ('pi' if '_pi-' in name else 'k')
        if match:historical.setdefault(component+':'+match.group(1),set()).add(r['partition'])
    nominal=set(json.loads((REPO/'ml/configs/low_energy.json').read_text())['nominal_runs'])
    records=[];candidates=[]
    for run in range(200080,200102):
        directory=Path(f'/eos/experiment/fasernu-data0/faser/sim/mc24/genie/{run}/rdo/s0014')
        paths=sorted(directory.glob('*.root'));known=[r for r in manifest if int(r['run'])==run]
        parsed=[]
        for f in paths:
            match=re.search(r'-(\d{5}-\d{5})-s0014',f.name)
            component='charm' if 'charm' in f.name else ('pi' if '_pi-' in f.name else 'k')
            group=component+':'+match.group(1) if match else 'unparsed'
            parsed.append((f,group))
        unassigned=[(f,g) for f,g in parsed if g not in roles and g not in historical and g!='unparsed']
        records.append(dict(run=run,kind='nominal' if run in nominal else 'alternative_flux',directory=str(directory),one_level_ROOT_files=len(paths),manifest_files=len(known),manifest_roles=json.dumps(Counter(r['partition'] for r in known),sort_keys=True),unassigned_generation_ranges=len(unassigned),historical_test_range_files=sum('test' in historical.get(g,set()) for _,g in parsed),generator_identity_verified=False,selected_low_energy_events='未测量'))
        # One deterministic candidate per run is only an input metadata contract, not a confirmation sample.
        if unassigned:
            f,g=unassigned[0]
            candidates.append(dict(run=run,path=str(f),group=g,file_bytes=f.stat().st_size,existing_group_roles=','.join(roles.get(g,[])) or 'unassigned in stage55 manifest',generation_seeds='未测量',parent_generator_ids='未测量',independence='unproven; filename/flux variation is insufficient',selection_yield='未测量'))
    assert len(candidates)<=24
    table(OUT/'supplement_runs.tsv',records);table(OUT/'supplement_candidates.tsv',candidates)
    save(OUT/'supplement_resources.json',dict(**resources(start),directory_listings=22,distinct_known_directories=22,recursive=False,candidate_file_stats=len(candidates),ROOT_headers_read=0,event_heads_read=0,new_reconstruction_jobs=0,new_independent_events_verified=0,known_developed_alternative_train_sources=31,known_developed_alternative_evaluation_sources=16,known_developed_low_energy_train_increment=139,note='Historical developed counts from stage55, not new yields; only directory and file metadata measured. Original files.tsv roles including test are inherited across flux/geometry before proposing candidates. Initial stage55-only metadata list was corrected before any header/event read; that first list was not a valid pilot proposal. Need generator identity/parent/seed before claiming independent support.'))
    print('directories',len(records),'candidate metadata',len(candidates),'listed files',sum(r['one_level_ROOT_files'] for r in records),'unassigned range-files',sum(r['unassigned_generation_ranges'] for r in records))


if __name__=='__main__':main()
