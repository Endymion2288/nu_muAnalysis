"""Batch pilot composition, generator metadata and native output QA."""
import csv
import json
from collections import defaultdict
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml'


def main():
    rows=list(csv.DictReader((OUT/'pilot_support.tsv').open(),delimiter='\t'));totals=defaultdict(lambda:defaultdict(float))
    for r in rows:
        k=(r['kind'],r['component'],r['selection'],r['stratum'])
        for n in ['N','old_incoming_overlap','new_proxy_N','weight_sum','HT_parent_estimate']:totals[k][n]+=float(r[n])
    records=[dict(zip(['kind','component','selection','stratum'],k),**v) for k,v in totals.items()]
    with (OUT/'pilot_totals.tsv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]),delimiter='\t');w.writeheader();w.writerows(records)
    evidence=json.loads((OUT/'production_evidence.json').read_text());sources={}
    for r in evidence:
        for q in r['evidence']:
            for line in q['lines']:
                if line['text'].startswith('Input File: '):sources.setdefault(line['text'][12:],[]).append(r['run'])
    result=[]
    for path,runs in sources.items():
        record=dict(path=path,runs=runs,exists=Path(path).is_file())
        if record['exists']:
            with uproot.open(path,array_cache=None) as f:
                record['trees']={}
                for name in f.keys(cycle=False):
                    t=f[name]
                    if not hasattr(t,'num_entries'):continue
                    record['trees'][name]=dict(entries=t.num_entries,branches=t.typenames())
                    # GENIE input EVNT is a TTree with native event objects or
                    # primitive kinematics. At most two rows, not pool scan.
                    wanted=[k for k in t.keys() if k in ['n','pdgc','status','px','py','pz','E','M','vx','vy','vz','W','Q2','y','x','event','iev','run']]
                    if wanted:record['trees'][name]['QA_first2']=ak.to_list(t.arrays(wanted,entry_stop=2))
                record['requested_bytes']=int(f.file.source.num_requested_bytes)
        result.append(record)
    (OUT/'generator_probe.json').write_text(json.dumps(result,indent=2)+'\n')
    print('SUMMARY',len(records),'generator files',len(result),flush=True)


if __name__=='__main__':main()
