#!/usr/bin/env python3
"""Concrete two-source training-support pilot contract; metadata only, no ROOT reads."""
import csv,json,re
from pathlib import Path
import numpy as np
from transfer_supervision import OUT,REPO,begin,resources,save


def identity(path):
    name=Path(path).name;m=re.search(r'-(\d{5}-\d{5})-s0014',name)
    component='charm' if 'charm' in name else ('pi' if '_pi-' in name else 'k')
    return component+':'+m.group(1) if m else None


def main():
    start=begin();historical={}
    for r in csv.DictReader((REPO/'ml/configs/files.tsv').open(),delimiter='\t'):
        key=identity(r['input_rdo'] or r['input']);historical.setdefault(key,set()).add(r['partition'])
    old=list(csv.DictReader((REPO/'ml/configs/low_energy_files.tsv').open(),delimiter='\t'))
    used={r['rdo'] for r in old if r['rdo']};rng=np.random.default_rng(2026110370);selected=[]
    for run,component in [(200080,'pi'),(200081,'k')]:
        directory=Path(f'/eos/experiment/fasernu-data0/faser/sim/mc24/genie/{run}/rdo/s0014')
        candidates=[]
        for f in sorted(directory.glob('*.root')):
            key=identity(f);roles=historical.get(key,set())
            if key and key.startswith(component+':') and 'train' in roles and not roles&{'test','validation','calibration'} and str(f) not in used:candidates.append((f,key,roles))
        assert candidates
        index=int(rng.integers(len(candidates)));f,key,roles=candidates[index]
        selected.append(dict(run=run,component=component,input_rdo=str(f),group=key,historical_roles=sorted(roles),role='training_support_pilot',already_in_stage55_alternative_manifest=False,eligible_source_files=len(candidates),selection_index=index,source_inclusion_probability=1/len(candidates),conditional_event_inclusion_probability=1.,file_bytes=f.stat().st_size,generator_parent_seed='未测量',independent_confirmation=False))
    cfg=dict(stage=70,prepared_in_stage=69,selection_seed=2026110370,selection='one uniform source file per fixed alternative pi/k run, sorted eligible canonical train ranges; complete selected file, no prefix or residual selection',sources=selected,
        purpose='measure added selected lowE core AND same-pz highE/high-y/uncertain-primary support after known incoming dedup; existing train generation ranges are development enrichment, not independent confirmation',
        identity_contract='inherit all historical canonical component/generation-range roles; never read test/cal/validation candidate events; remove exact incoming(pdg,px,py,pz) already in all stage55 developed cache and duplicates within the pilot; parent generator ID/subfile/seed remains required for any independence claim',
        reconstruction_contract='common nominal d32b0ff3 without IFT TI12MC04 FASERNU-04 OFLCOND-FASER-06; verify actual compatible existing build before use, no guessed geometry or alternative raw',
        selection_contract='same stage55 pz>50 GeV original cuts and leading/vertex; no E ceiling or fitted-charge cut change',
        feature_contract='same62 audited pz0/raw11/reduced/status/dependency/typed NaN; no new variables or imputation, retain missing and all difficult tails',
        input_limit=dict(source_files=2,metadata_heads_events_total=40,full_source_events_total_max=20000),
        proposed_budget=dict(condor_jobs_max=2,cpus_per_job_max=2,memory_MB=3000,total_CPU_s_max=7200,per_job_wall_s_max=3600,retained_bytes_max=5000000),
        budgets_and_selection_yields='未测量; first <=40 schema/identity heads and small native resource QA must precede full2-file pilot freeze; no scale-up if cap incompatible',
        output_contract='counts by true50-100/100-200 core, same reco pz50-100 true>=200/high-y, unconfirmed and high-end; raw readout validity/missing N, exact incoming reuse/new key counts, actual CPU/RSS/I/O and inclusion probabilities; compact selected data only if needed, delete snapshots/PHYS duplicates',
        stopping='0 energy model fits/0 spectral toys; after the2-source pilot report measured new support or0 and stop. No all-run production. If no new support after dedup, issue concrete new pi/k generator parent/seed request; no methods/metadata loop.',
        future_confirmation='requires genuinely new generator kinematics/parents and random untouched source pool, not these inherited train ranges',
        executed=False)
    path=REPO/'ml/configs/alternative_support_pilot.json';assert not path.exists();save(path,cfg)
    save(OUT/'followup_preparation.json',dict(**resources(start),directory_listings=2,recursive=False,files_statted=2,ROOT_headers_read=0,events_read=0,reconstruction_jobs=0,sources=selected,config=str(path.relative_to(REPO))))
    print(json.dumps(selected,indent=2))


if __name__=='__main__':main()
