"""Batch-only bounded native schema/units probe, no training or selection scan."""
import json
import multiprocessing as mp
import resource
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'workbook/stage119_energy_ml'


def probe(source):
    start=time.perf_counter();cpu=time.process_time()
    with uproot.open(source['input'],array_cache=None) as f:
        result=dict(source=source,keys=[str(k) for k in f.keys()],trees={})
        for name in f.keys(cycle=False):
            tree=f[name]
            if not hasattr(tree,'num_entries'):continue
            result['trees'][name]=dict(entries=tree.num_entries,branches=tree.typenames())
        if source.get('product','phy')=='phy':
            t=f['nt'];wanted=['run','eventID','Track_pz0','Track_isForward']
            wanted += [f'Calo{i}_{k}' for i in range(4) for k in ['E_EM','charge','status']]
            wanted += [f'VetoNu{i}_{k}' for i in range(2) for k in ['raw_charge','reduced_charge','status','localtime']]
            wanted=[k for k in wanted if k in t]
            a=t.arrays(wanted,entry_stop=1)
            result['first_identity_QA']=ak.to_list(a)
        result['requested_bytes']=int(f.file.source.num_requested_bytes)
    result.update(CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-start)
    return result


def main():
    start=time.perf_counter();p=json.loads((OUT/'protocol.json').read_text())
    sources=[s for s in p['sources'] if s['probe']]+p['extra']
    with mp.get_context('fork').Pool(8) as pool:r=pool.map(probe,sources)
    (OUT/'schema_probe.json').write_text(json.dumps(dict(files=r,new_fits=0,forward=0,
        QA_identities=sum(s.get('product','phy')=='phy' for s in sources),
        requested_bytes=sum(x['requested_bytes'] for x in r),wall_s=time.perf_counter()-start,
        max_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),indent=2,allow_nan=True)+'\n')
    print('Probe complete',len(sources),'files',flush=True)


if __name__=='__main__':main()
