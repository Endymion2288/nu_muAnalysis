"""Inspect the exact generator products adjacent to the certified Pythia EVNT."""
import json
from pathlib import Path

import awkward as ak
import uproot

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml'


def main():
    paths=json.loads((OUT/'genie_contract.json').read_text())['inputs'];result=[]
    for path in paths:
        with uproot.open(path,array_cache=None) as f:
            r=dict(input=path,trees={})
            for name in f.keys(cycle=False):
                t=f[name]
                if not hasattr(t,'num_entries'):continue
                b=t.typenames();r['trees'][name]=dict(entries=t.num_entries,branches=b)
                primitive=[k for k,v in b.items() if 'genie' not in v.lower() and k in ['W','Q2','y','x','n','pdgc','status','px','py','pz','E','M','vx','vy','vz','event','iev']]
                if primitive:r['trees'][name]['QA_first2']=ak.to_list(t.arrays(primitive,entry_stop=2))
            r['requested_bytes']=int(f.file.source.num_requested_bytes);result.append(r)
    (OUT/'genie_schema.json').write_text(json.dumps(result,indent=2)+'\n')
    print('GENIE metadata complete',len(paths),flush=True)


if __name__=='__main__':main()
