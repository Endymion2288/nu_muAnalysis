"""Compact redundant manifests and normalize display-only whitespace losslessly."""
import csv
import gzip
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage131_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage131'


def save_exact(name,value):
    encoded=json.dumps(value,separators=(',',':'))
    with gzip.open(CACHE/name,'wt') as stream:stream.write(encoded)
    with gzip.open(CACHE/name,'rt') as stream:assert stream.read()==encoded


def main():
    assert not (OUT/'display_finalization.json').exists()
    manifests={p.name:json.loads(p.read_text()) for p in OUT.glob('*_submission*.json')}
    save_exact('submission_manifests.json.gz',manifests)
    removed=0;files=0
    for name,record in manifests.items():
        path=OUT/name;before=path.stat().st_size
        if name.endswith('_submission.json'):
            path.unlink();removed+=before;files+=1;continue
        compact=dict(record);compact['package']=dict(record['package'])
        inventory=compact['package'].pop('files')
        compact['package']['files_N']=len(inventory)
        compact['package']['full_inventory']=f'ntuples/energy_ml_stage131/submission_manifests.json.gz:{name}'
        path.write_text(json.dumps(compact,indent=2)+'\n');removed+=before-path.stat().st_size
    tables={p.name:p.read_text() for p in OUT.glob('*.tsv')}
    save_exact('original_display_tables.json.gz',tables)
    for name,text in tables.items():
        reader=csv.DictReader(io.StringIO(text),delimiter='\t');keys=reader.fieldnames;rows=list(reader)
        with (OUT/name).open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=keys,delimiter='\t',lineterminator='\n');writer.writeheader()
            writer.writerows({k:('NA' if row[k] is None or row[k]=='' else row[k]) for k in keys} for row in rows)
        reread=list(csv.DictReader((OUT/name).open(),delimiter='\t'))
        assert len(reread)==len(rows)
        for a,b in zip(rows,reread):
            for key in keys:
                if a[key] is not None and a[key]!='':assert a[key]==b[key]
    svg=OUT/'energy_comparisons.svg';svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    cleanup=json.loads((OUT/'cleanup.json').read_text())
    cleanup['initial_cleanup_removed_logical_B']=cleanup['removed_logical_duplicate_B']
    cleanup['manifest_dedup_removed_logical_B']=removed
    cleanup['removed_logical_duplicate_B']+=removed;cleanup['retired_files']+=files
    cleanup['retained_B']['ntuples/energy_ml_stage131']=sum(p.stat().st_size for p in CACHE.rglob('*') if p.is_file())
    (OUT/'cleanup.json').write_text(json.dumps(cleanup,indent=2)+'\n')
    result=dict(passed=True,manifest_records=len(manifests),deleted_latest_mirror_files=files,manifest_removed_logical_B=removed,tables=len(tables),nonempty_table_cells_exact=True,missing_display_cells='NA; original empty fields retained in ignored original_display_tables.json.gz',SVG='line-ending whitespace only; already visually checked plot unchanged',original_manifest_archive='ntuples/energy_ml_stage131/submission_manifests.json.gz',no_event_or_model_changes=True)
    (OUT/'display_finalization.json').write_text(json.dumps(result,indent=2)+'\n');print(result);print(cleanup)


if __name__=='__main__':main()
