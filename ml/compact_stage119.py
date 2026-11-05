"""Byte-verified local archival of event-level evidence and transport cleanup."""
import argparse
import json
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage119'


def main(remove):
    names=['production_contract.json','pythia_production_contract.json','fit_task_lock.json','window4.json',
           'genie_identity_probe.json','same_N_correction_lock.json','schema_probe.json']
    names += [f'hits_{r}_hits.json' for r in [200184,200110,200113,200300,200303]]
    names += [f'pythia_parent_{i}.json' for i in range(18)]
    paths=[OUT/n for n in names];archive=CACHE/'persisted_evidence.tar.gz'
    assert all(p.is_file() for p in paths)
    with tarfile.open(archive,'w:gz',compresslevel=6) as t:
        for p in paths:t.add(p,arcname=str(p.relative_to(ROOT)))
    with tarfile.open(archive) as t:
        for p in paths:assert t.extractfile(str(p.relative_to(ROOT))).read()==p.read_bytes()
    rows=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size) for p in paths]
    # Keep reviewable source/probability/resource specifications in Git;
    # response identities and event arrays belong in the retained data archive.
    for name in ['production_contract','pythia_production_contract']:
        d=json.loads((OUT/(name+'.json')).read_text());requests=[]
        for r in d['requests']:
            requests.append({**{k:v for k,v in r.items() if k not in ['entries','eventID','incoming']},'reconstructed_N':len(r['entries'])})
        d['requests']=requests;d['event_level_evidence']=str(archive.relative_to(ROOT))
        (OUT/(name+'_summary.json')).write_text(json.dumps(d,indent=2)+'\n')
    lock=json.loads((OUT/'same_N_correction_lock.json').read_text())
    lock={k:v for k,v in lock.items() if k!='old_rows'}
    lock['event_level_evidence']=str(archive.relative_to(ROOT))
    (OUT/'same_N_correction_lock_summary.json').write_text(json.dumps(lock,indent=2)+'\n')
    schema=json.loads((OUT/'schema_probe.json').read_text())
    for item in schema['files']:
        examples=item.pop('first_identity_QA',[])
        item['first_identity_QA_N']=len(examples)
    schema['event_level_evidence']=str(archive.relative_to(ROOT))
    (OUT/'schema_probe_summary.json').write_text(json.dumps(schema,indent=2)+'\n')
    record=dict(archive=str(archive.relative_to(ROOT)),archive_bytes=archive.stat().st_size,uncompressed_bytes=sum(r['bytes'] for r in rows),
        byte_verified=True,files=rows,restore_command=f'tar -xzf {archive.relative_to(ROOT)} -C .',removed_expanded_files=remove)
    (OUT/'persisted_evidence.json').write_text(json.dumps(record,indent=2)+'\n')
    if remove:
        for p in paths:p.unlink()
    print(json.dumps({k:v for k,v in record.items() if k!='files'}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--remove-expanded',action='store_true');a=p.parse_args();main(a.remove_expanded)
