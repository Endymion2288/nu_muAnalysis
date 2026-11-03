#!/usr/bin/env python3
"""Independent stdlib check of identities, frozen counts and activity arithmetic."""
import argparse
import csv
import json
import math
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();directory=args.directory
    sample=json.loads((directory/'sample.json').read_text())
    seen=set();identities=set();sums={};n={};invalid=[];io=0
    source_sums={};source_n={}
    qa=json.loads((args.output/'qa.json').read_text())
    pilot={(r['source'],0):r['records'][0]['values']
           for q in qa['successful_native_qa'] for r in q['sources']}
    for path in sorted(directory.glob('native_*.json')):
        result=json.loads(path.read_text());io+=result['bytes_read']
        for source in result['sources']:
            row=sample['sources'][source['source']]
            assert not source['unresolved']
            assert source['matched']==source['requested']==len(row['cases'])
            for record in source['records']:
                key=(row['source'],record['case']);assert key not in seen;seen.add(key)
                case=row['cases'][record['case']]
                identity=(row['source'],record['native_file'],record['native_entry'])
                assert identity not in identities;identities.add(identity)
                assert record['event']==case['event']
                if row['sample']=='data':assert record['timestamp']==case['eventTime']
                else:assert record['native_entry']==case['entry']
                values=record['values']
                assert [v[3] for v in values]==case['original_counts'][:4]
                if key in pilot:
                    assert [v[:22] for v in values]==[v[:22] for v in pilot[key]]
                values=[v+[0]*(25-len(v)) for v in values]
                for st,v in enumerate(values):
                    assert all(isinstance(x,int) and x>=0 for x in v)
                    assert sum(v[17:22])==v[3]
                    assert sum(v[9:17])==v[0]
                    assert v[2]<=v[1]<=v[0]
                    assert v[22]<=v[4]<=v[3]
                    assert v[4]+v[23]<=v[3]
                    assert v[6]<=36864
                    if v[23]:invalid.append(dict(source=row['source'],case=record['case'],event=record['event'],
                        native_entry=record['native_entry'],station=st,clusters=v[23],strip_ids=v[24]))
                kind=row['sample'];n[kind]=n.get(kind,0)+1
                source_n[row['source']]=source_n.get(row['source'],0)+1
                for st in [0,1,2,3,'common']:
                    vector=values[st] if st!='common' else [sum(values[i][j] for i in [1,2,3]) for j in range(25)]
                    target=sums.setdefault((kind,str(st)),[0]*25)
                    source_target=source_sums.setdefault((row['source'],str(st)),[0]*25)
                    for j,value in enumerate(vector):
                        target[j]+=value;source_target[j]+=value
    assert len(seen)==4096 and n=={'MC':2048,'data':2048},n
    observable_index=dict(raw_strips=0,outside_strips=1,isolated_outside_strips=2,clusters=3,
        outside_clusters=4,outside_singleton_clusters=5,measured_wafers=7,
        isolated_outside_clusters=22,unknown_cluster_geometry=23,invalid_cluster_strip_ids=24)
    draws=json.loads((args.output/'bootstrap_sources.json').read_text())
    assert all(len(v)==500 for v in draws.values())
    def quantile(values,probability):
        ordered=sorted(values);position=(len(ordered)-1)*probability;left=math.floor(position)
        return ordered[left]+(ordered[min(left+1,len(ordered)-1)]-ordered[left])*(position-left)
    checked=0;max_delta=0;max_interval_delta=0
    with (args.output/'activity.tsv').open() as stream:
        for row in csv.DictReader(stream,delimiter='\t'):
            if row['layer']!='all' or row['observable'] not in observable_index:continue
            expected=sums[(row['kind'],row['station'])][observable_index[row['observable']]]/n[row['kind']]
            delta=abs(expected-float(row['mean']));assert delta<1e-12;max_delta=max(max_delta,delta);checked+=1
            index=observable_index[row['observable']]
            boot=[sum(source_sums[(s,row['station'])][index] for s in draw)/sum(source_n[s] for s in draw)
                  for draw in draws[row['kind']]]
            for p,key in [(.025,'low95'),(.975,'high95')]:
                delta=abs(quantile(boot,p)-float(row[key]));assert delta<1e-10
                max_interval_delta=max(max_interval_delta,delta)
    report=dict(passed=True,unique_source_case=len(seen),unique_native_identity=len(identities),events=n,
                qa_fingerprint_closure=len(pilot),independent_means=checked,max_mean_delta=max_delta,
                independent_source_intervals=checked,max_interval_delta=max_interval_delta,
                native_bytes_read=io,invalid_cluster_cases=invalid,
                limitations='Identity/count/mean validation; no certified active denominator or pure-noise identification')
    (args.output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()
