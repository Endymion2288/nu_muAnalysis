#!/usr/bin/env python3
"""Freeze source/entry identities without selecting on tracker probe counts."""
import argparse
import json
import resource
import time
from pathlib import Path

import numpy as np
import uproot

from calonu_muon_control import manifest
from read_f6_muon_response import REPO, TRACKS, VETO, branches, configuration, select


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    cfg = configuration()
    start, cpu = time.perf_counter(), time.process_time()
    results = []
    for source in ([0, 6] if args.smoke else range(12)):
        row = manifest(REPO)[source]
        with uproot.open(row['input']) as f:
            tree = f['nt']
            assert tree.num_entries == 50000
            # One read per source reuses baskets; no fixed entry-chunk reread.
            arr = tree.arrays(branches(), entry_stop=4 if args.smoke else None)
            values, flow, keep = select(arr, 'MC', {}, cfg, include_mask=True)
            entries = np.flatnonzero(keep)
            assert len(entries) == flow['unit_reco_charge']
            chosen = []
            for pbin, (low, high) in enumerate([(100000, 250000), (250000, 1000000)]):
                candidates = np.flatnonzero((values['Track_p0'] >= low) & (values['Track_p0'] < high))
                cell = 2*source+pbin
                n = 85+int(cell in [0, 3, 6, 9, 12, 15, 18, 21])
                rng = np.random.default_rng(np.random.SeedSequence([2026110253, source, pbin]))
                assert args.smoke or len(candidates) >= n
                for j in rng.permutation(candidates)[:n]:
                    chosen.append(dict(entry=int(entries[j]), event=int(values['eventID'][j]), pbin=pbin,
                        original_counts=[int(values[k][j]) for k in ['nClusters0','nClusters1','nClusters2','nClusters3','SpacePoints','TrackSegments']],
                        track=[float(values['Track_'+k][j]) for k in TRACKS],
                        veto_raw_pC=[float(values[k+'_raw_charge'][j]) for k in VETO]))
            chosen.sort(key=lambda x:x['entry'])
            rdo = row['input'].replace('/bck/', '/rdo/').replace('-PHYS.root','-RDO.root')
            results.append(dict(source=source,run=int(row['run']),input_phys=row['input'],input_rdo=rdo,
                total_entries=tree.num_entries,cutflow=flow,requested_bytes=int(f.file.source.num_requested_bytes),cases=chosen))
    output = dict(seed=2026110253,smoke=args.smoke,sources=results,
        wall_s=time.perf_counter()-start,cpu_s=time.process_time()-cpu,
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    if not args.smoke:
        assert sum(len(r['cases']) for r in results)==2048
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,separators=(',',':'))+'\n')
    print(json.dumps({k:v for k,v in output.items() if k!='sources'}),flush=True)


if __name__=='__main__':
    main()
