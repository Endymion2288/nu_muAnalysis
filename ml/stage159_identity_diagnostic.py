"""Explain zero fixed-prefix matches using the same named PHYS identity index."""
import json
import resource
import time
from collections import Counter
from pathlib import Path

import numpy as np
import uproot

OUT=Path('workbook/stage159_energy_ml')


def main():
    tick,cpu=time.perf_counter(),time.process_time()
    plan=json.loads((OUT/'protocol.json').read_text())
    native=json.loads((OUT/'native_64.json').read_text())['records']
    original=json.loads((OUT/'summary.json').read_text())
    with uproot.open(plan['sources']['PHYS'],array_cache=None) as source:
        tree=source['nt'];keys=set(tree.keys())
        columns=['run','eventID','eventTime']
        data=tree.arrays(columns,library='np')
        run,event,stamp=[data[k] for k in columns]
        counts=Counter(zip(run.tolist(),event.tolist()))
        ids=Counter(event.tolist())
        per_run=[]
        for value in np.unique(run):
            mask=run==value
            per_run.append(dict(run=int(value),N=int(mask.sum()),event_min=int(event[mask].min()),
                event_max=int(event[mask].max()),timestamp_min=int(stamp[mask].min()),timestamp_max=int(stamp[mask].max())))
        checks=[]
        for r in native:
            matches=counts[(r['run'],r['event'])]
            checks.append(dict(native_entry=r['entry'],native_run=r['run'],native_event=r['event'],native_timestamp=r['timestamp'],
                exact_key_matches=matches,event_number_matches_any_run=ids[r['event']]))
        unique=sum(r['exact_key_matches']==1 for r in checks)
        assert unique==original['unique_pair_N']
        first=[dict(entry=i,run=int(run[i]),event=int(event[i]),timestamp=int(stamp[i])) for i in range(min(8,len(run)))]
        raw_branches=sorted(k for k in keys if k.endswith('_raw_charge'))
        read_bytes=int(source.file.source.num_requested_bytes)
    summary=dict(passed=True,independent_strict_identity_matches_N=unique,original_strict_identity_matches_N=original['unique_pair_N'],
        native_parent_N=len(native),native_event_min=min(r['event'] for r in native),native_event_max=max(r['event'] for r in native),
        native_timestamp_min=min(r['timestamp'] for r in native),native_timestamp_max=max(r['timestamp'] for r in native),
        PHYS_by_run=per_run,PHYS_first8=first,checks=checks,actual_raw_charge_branch_names=raw_branches,
        native_prefix_event_range_below_all_PHYS=bool(all(r['event']<int(event.min()) for r in native)),
        native_prefix_time_range_before_all_PHYS=bool(all(r['timestamp']<int(stamp.min()) for r in native)),
        read_bytes=read_bytes,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
        RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        interpretation='Exact identities unchanged; no alternative pairing, source substitution, native parent expansion or raw/energy fit. Range exclusion identifies support absence; upstream producer selection remains uncertified.')
    (OUT/'identity_diagnostic.json').write_text(json.dumps(summary,indent=2)+'\n')
    print({k:v for k,v in summary.items() if k!='checks'},flush=True)


if __name__=='__main__':main()
