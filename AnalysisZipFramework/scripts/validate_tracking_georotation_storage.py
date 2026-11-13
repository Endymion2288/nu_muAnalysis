#!/usr/bin/env python3
"""Read back every merged array against its source before removing redundant stage201 outputs."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor

import numpy as np


def equal(a,b):
    return np.array_equal(a,b,equal_nan=np.asarray(a).dtype.kind in 'fc')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--combined',type=Path,required=True)
    p.add_argument('--local-shards',type=Path,required=True)
    p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--remove',action='store_true')
    p.add_argument('--details-manifest',type=Path)
    p.add_argument('--details-combined',type=Path)
    args=p.parse_args()
    records=[line.split('\t') for line in args.manifest.read_text().splitlines()]
    with np.load(args.combined/'paired_results.npz') as f:counts={k:f[k] for k in f.files}
    with np.load(args.combined/'fiducial_events.npz') as f:events={k:f[k] for k in f.files}
    with np.load(args.combined/'candidate_diagnostics.npz') as f:candidates={k:f[k] for k in f.files}
    performance={int(r['index']):r for r in csv.DictReader((args.combined/'performance.tsv').open(),delimiter='\t')}
    assert len(records)==343
    assert equal([int(r[0]) for r in records],counts['manifest_indices'])
    assert equal(counts['manifest_indices'],events['manifest_indices'])
    assert equal(counts['manifest_indices'],candidates['manifest_indices'])
    rows=[]
    for i,record in enumerate(records):
        path=args.local_shards/Path(record[5]).name
        with np.load(path) as f:
            keys=[]
            for key in counts:
                if key not in ('manifest_indices','runs'):
                    assert equal(counts[key][i],f[key]),(record[0],key)
                    keys.append(key)
            start,stop=events['file_offsets'][i:i+2]
            for key in f.files:
                if key.startswith('event_'):
                    assert equal(events[key][start:stop],f[key]),(record[0],key)
                    keys.append(key)
            for key,prefix in [('tracks','track'),('pairs','pair'),('migrations','migration')]:
                start,stop=candidates[prefix+'_file_offsets'][i:i+2]
                assert equal(candidates[key][start:stop],f[key]),(record[0],key)
                keys.append(key)
            for key in ('track_fields','pair_fields'):
                assert equal(candidates[key],f[key]),key
                keys.append(key)
            for key in ('effective_reco_json','software_provenance_json'):
                target=('effective_reco.json' if key=='effective_reco_json' else 'software_provenance.json')
                assert json.loads(str(f[key]))==json.loads((args.combined/target).read_text()),key
                keys.append(key)
            perf=performance[int(record[0])]
            assert perf['host']==str(f['host'])
            assert int(perf['output_bytes'])==path.stat().st_size
            for step,line in json.loads(str(f['performance_json'])).items():
                for key,value in re.findall(r'(\w+)=([0-9.]+)',line):
                    assert float(perf[step+'_'+key])==float(value),(record[0],step,key)
            for key,value in json.loads(str(f['root_file_bytes_json'])).items():
                if key in ('input-RDO.root','input-xAOD.root','forward.root','backward.root','merge.root'):
                    assert int(perf[key[:-5].replace('-','_')+'_bytes'])==value
            keys+=['performance_json','host','root_file_bytes_json']
            if 'split_job_metadata_json' in f:
                assert json.loads(str(f['split_job_metadata_json']))==json.loads((args.combined/'recovery53_audit.json').read_text())['parts']
                keys.append('split_job_metadata_json')
            assert set(keys)==set(f.files)-{'manifest_index'},(record[0],set(f.files)-set(keys))
            rows.append(dict(index=int(record[0]),events=int(f['counts'][0,0]),
                source_bytes=path.stat().st_size,checked_key_count=len(keys),source=record[5]))
    from report_tracking_georotation import numerical_tables
    numerical_tables(candidates, args.audit.parent)
    retained={p.name:p.stat().st_size for p in args.combined.glob('*.npz')}
    audit=dict(files=len(records),events=sum(r['events'] for r in rows),
        exact_array_readback=True,source_bytes=sum(r['source_bytes'] for r in rows),
        retained_npz_bytes=retained,metadata_preserved_in=['input_manifest.tsv','performance.tsv',
            'effective_reco.json','software_provenance.json','recovery53_audit.json'],
        checked_keys=keys,sources=rows,removed=False)
    assert audit['events']==3384987
    if args.details_manifest:
        records=[r.split('\t') for r in args.details_manifest.read_text().splitlines()]
        with gzip.open(args.details_combined/'diagnostics.json.gz','rt') as f:detail=json.load(f)
        assert len(records)==len(detail)==212
        staged=args.local_shards/'details';staged.mkdir(exist_ok=True)
        def check(item):
            record,event=item
            target=staged/Path(record[-1]).name
            subprocess.run(['xrdcp','--silent','root://eoshome-x.cern.ch/'+record[-1],str(target)],check=True)
            source=json.loads(target.read_text())
            assert json.dumps(source,allow_nan=True,separators=(',',':'))==json.dumps(event,allow_nan=True,separators=(',',':'))
            assert (event['run'],event['event'])==(int(record[1]),int(record[2]))
            return dict(run=event['run'],event=event['event'],source=record[-1],source_bytes=target.stat().st_size)
        with ThreadPoolExecutor(max_workers=4) as pool:detail_rows=list(pool.map(check,zip(records,detail)))
        audit['details']=dict(events=len(detail_rows),exact_json_readback=True,
            source_bytes=sum(r['source_bytes'] for r in detail_rows),
            combined_bytes=(args.details_combined/'diagnostics.json.gz').stat().st_size,sources=detail_rows)
    args.audit.write_text(json.dumps(audit,indent=2)+'\n')
    if args.remove:
        for r in rows:subprocess.run(['xrdfs','root://eoshome-x.cern.ch','rm',r['source']],check=True)
        for r in audit.get('details',{}).get('sources',[]):
            subprocess.run(['xrdfs','root://eoshome-x.cern.ch','rm',r['source']],check=True)
        audit['removed']=True
        args.audit.write_text(json.dumps(audit,indent=2)+'\n')
    display={k:v for k,v in audit.items() if k not in ('sources','details')}
    if 'details' in audit:display['details']={k:v for k,v in audit['details'].items() if k!='sources'}
    print(json.dumps(display))


if __name__=='__main__':
    main()
