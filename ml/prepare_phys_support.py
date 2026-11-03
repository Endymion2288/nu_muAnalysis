"""Stage81: freeze known train PHYS pools before inspecting any event outcomes."""
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from audited_features import REPO
from support_augmentation import begin, resources, save

OUT = REPO/'workbook/stage81_energy_ml'
CACHE = REPO/'ntuples/energy_ml_stage81'
SEED = 2026110377


def identity(path):
    name = Path(path).name
    match = re.search(r'-(\d{5}-\d{5})-s0014', name)
    component = 'charm' if 'charm' in name else 'pi' if '_pi-' in name else 'k'
    return component+':'+match.group(1) if match else None


def main():
    start = begin(); OUT.mkdir(exist_ok=True); CACHE.mkdir(exist_ok=True)
    assert not (OUT/'source_plan.json').exists()
    base = list(csv.DictReader((REPO/'ml/configs/files.tsv').open(), delimiter='\t'))
    low = list(csv.DictReader((REPO/'ml/configs/low_energy_files.tsv').open(), delimiter='\t'))
    roles = {}
    for r in base+low:
        key = identity(r.get('input_rdo') or r.get('rdo') or r['input'])
        roles.setdefault(key, set()).add(r['partition'])
    # Complete pz>50 extraction, including scratch-produced sources, is identified
    # by run/group rather than by path aliases. Stage55 source257 was not delivered.
    complete = {(int(r['run']),r['group']) for r in low if int(r['index']) != 257}
    complete.add((200080,'pi:00440-00449'))
    candidates = []; unavailable = []
    # Explicit existing manifest paths for pi; K uses only the one known PHYS
    # directory specified by file_config.yaml, not an EOS-wide discovery scan.
    for r in base:
        if int(r['run']) != 200080: continue
        key = identity(r['input']); rr = roles[key]
        if 'train' not in rr or rr & {'test','validation','calibration'}: continue
        if (200080,key) in complete: continue
        path = Path(r['input'])
        record = dict(run=200080,component='pi',group=key,input=str(path),historical_roles=sorted(rr),
                      known_entry='ml/configs/files.tsv:'+r['index'],PHYS_kind='d32b0ff3 merge without IFT')
        if path.is_file(): record['file_bytes']=path.stat().st_size; candidates.append(record)
        else: unavailable.append(record)
    directory = Path('/eos/experiment/fasernu-data0/faser/sim/mc24/genie/200081/bck/s0014')
    for path in sorted(directory.glob('*-PHYS.root')):
        key = identity(path); rr = roles.get(key,set())
        if 'train' not in rr or rr & {'test','validation','calibration'}: continue
        if (200081,key) in complete: continue
        candidates.append(dict(run=200081,component='k',group=key,input=str(path),historical_roles=sorted(rr),
            known_entry='AnalysisZipFramework/config/file_config.yaml run200081 data_paths',
            PHYS_kind='existing configured bck PHYS; schema/conditions not yet verified',file_bytes=path.stat().st_size))
    rng = np.random.default_rng(SEED); selected = []; pools = {}
    for comp in ['pi','k']:
        pool = sorted([r for r in candidates if r['component']==comp], key=lambda r:r['input'])
        n = min(2,len(pool)); indices = sorted(rng.choice(len(pool),size=n,replace=False).tolist()) if n else []
        pools[comp] = dict(available_N=len(pool),selected_indices=indices,source_probability=n/len(pool) if pool else None)
        for i in indices:
            selected.append(dict(pool[i],index=len(selected),source_probability=n/len(pool),conditional_event_probability=1.,
                                 selection_index=i,independent_confirmation=False,role='development_enrichment'))
    save(OUT/'source_plan.json',dict(stage=81,seed=SEED,frozen_utc=datetime.now(timezone.utc).isoformat(),
        protocol='docs/nu_mu_energy_ml_support_delivery_prompt.md original stage77 unchanged',
        roles_by_canonical_group={k:sorted(v) for k,v in sorted(roles.items())},complete_run_groups=sorted([list(x) for x in complete]),
        candidates=candidates,unavailable=unavailable,pools=pools,sources=selected,
        QA_entries_per_source=10,QA_total_max=40,event_data_read_before_freeze=0,
        proposed_limits=dict(source_files=4,input_events=40000,input_bytes=10000000000,Condor_jobs=4,CPUs_each_max=2,
                             memory_MB_each=3000,total_CPU_s=7200,wall_each_s=3600,retained_bytes=10000000),
        actual_resources='not frozen; actual selected-source QA precedes submission',energy_fits=0,
        genealogy='unknown full parent/subfile/entry/seed; inherited train/challenge is development only',**resources(start)))
    print(json.dumps(dict(pools=pools,sources=selected,**resources(start)),indent=2))


if __name__=='__main__': main()
