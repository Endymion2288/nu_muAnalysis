"""Uniform full-file parent pilot. No model outcomes and no confirmation risk."""
import csv
import json
import multiprocessing as mp
import resource
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot
import yaml

from stage112_selection import BRANCHES, active_cuts, derive

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage119_energy_ml'
CACHE = ROOT/'ntuples/energy_ml_stage119'


def work(s):
    tick, cpu = time.perf_counter(), time.process_time()
    extra = [f'Calo{j}_{k}' for j in range(4) for k in ['charge', 'E_EM', 'status']]
    extra += [f'{v}_{k}' for v in ['VetoNu0', 'VetoNu1', 'Veto10', 'Veto20', 'Veto21']
              for k in ['localtime', 'triggertime']]
    with uproot.open(s['input'], array_cache=None) as f:
        tree = f['nt']; missing = sorted(set(BRANCHES)-set(tree.keys()))
        # These old PHYS omit only the barcode used for association diagnostics.
        # Unknown barcodes remain unknown; no inferred association/family ID.
        assert set(missing) <= {'truth_barcode'}, missing
        a = tree.arrays([k for k in dict.fromkeys(BRANCHES+extra) if k in tree])
        if missing:
            a = ak.with_field(a, ak.ones_like(a.truth_pdg, dtype=float)*np.nan, 'truth_barcode')
        d, flags = derive(a)
        cuts = active_cuts(yaml.safe_load((ROOT/'AnalysisZipFramework/config/ml_low_energy_cuts.yaml').read_text()))
        assert set(n for n, _ in cuts) == set(flags)
        selected = np.logical_and.reduce([flags[n][0] for n, _ in cuts])
        g0 = np.logical_and.reduce([flags[n][0] for n, _ in cuts if n != 'Track pz > 50 GeV'])
        data = {k: d[k] for k in ['incoming', 'run', 'eventID', 'E', 'pz', 'y', 'vertex_z', 'vertex_r', 'Emu', 'primary_valid', 'confirmed']}
        data.update(S50=selected, G0=g0, input_entry=np.arange(len(a)),
                    association_known=np.full(len(a), not bool(missing)))
        for k in extra:
            data[k] = ak.to_numpy(a[k])
        np.savez_compressed(CACHE/f'pilot_{s["index"]}.npz', **data)
        q = dict(source=s, parent_N=len(a), selected_N=int(selected.sum()),
                 missing_diagnostic_branches=missing, cutflow={}, resources={})
        cumulative = np.ones(len(a), bool)
        for n, _ in cuts:
            cumulative &= flags[n][0]
            q['cutflow'][n] = int(cumulative.sum())
        q['resources'] = dict(requested_bytes=int(f.file.source.num_requested_bytes),
                              compressed_branch_bytes=sum(tree[k].compressed_bytes for k in set(BRANCHES+extra) if k in tree),
                              CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
                              worker_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return q


def main():
    tick = time.perf_counter(); CACHE.mkdir(parents=True, exist_ok=True)
    p = json.loads((OUT/'protocol.json').read_text())
    with mp.get_context('fork').Pool(8) as pool:
        results = pool.map(work, p['sources'])
    # Full old selected exposure, including all quarantine, and every support
    # view ever loaded in the earlier expansion studies. This is an incoming
    # veto only; it cannot certify all unpersisted historical parent identities.
    old = []
    for name in json.loads((OUT/'exposure_inputs.json').read_text()):
        with np.load(ROOT/name) as z:
            if 'incoming' in z:
                old.extend(map(tuple, z['incoming']))
    old = set(old); rows = []; unique = {}; allkeys = []
    for q in results:
        s = q['source']; z = np.load(CACHE/f'pilot_{s["index"]}.npz')
        keys = list(map(tuple, z['incoming'])); finite = np.isfinite(z['incoming']).all(1)
        overlap = np.array([k in old for k in keys])
        # Incoming views receive one total unit before any selection.
        _, inv, counts = np.unique(z['incoming'], axis=0, return_inverse=True, return_counts=True)
        w = 1/counts[inv]
        e, pz, y = (z[k] for k in ['E', 'pz', 'y'])
        layers = dict(all=np.ones(len(e), bool), low50_100=(e>=50)&(e<100),
                      low100_200=(e>=100)&(e<200), lowpz_highE=(pz>=50)&(pz<100)&(e>=200),
                      high_y=y>=.8, highE=e>=1000, upstream=z['vertex_z']<-2200)
        for selection in ['parent', 'G0', 'S50']:
            selected = np.ones(len(e), bool) if selection=='parent' else z[selection]
            for layer, mask in layers.items():
                take = selected & mask; nw = w[take]; independent = take & finite & ~overlap
                rows.append(dict(run=s['run'], index=s['index'], component=s['component'], kind=s['kind'],
                    selection=selection, stratum=layer, N=int(take.sum()), incoming=len(set(k for k,m in zip(keys,take) if m)),
                    old_incoming_overlap=int((take & overlap).sum()), new_proxy_N=int(independent.sum()),
                    ESS=float(nw.sum()**2/(nw@nw)) if len(nw) else 0,
                    file_probability=s['file_inclusion_probability'], weight_sum=float(nw.sum()),
                    HT_parent_estimate=float(take.sum()/s['file_inclusion_probability'])))
        q['old_incoming_overlap_parent_N']=int(overlap.sum())
        q['finite_incoming_parent_N']=int(finite.sum())
        allkeys.extend(keys)
        z.close()
    with (OUT/'pilot_support.tsv').open('w') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0]), delimiter='\t');w.writeheader();w.writerows(rows)
    result=dict(files=results, parent_N=sum(q['parent_N'] for q in results),
        selected_N=sum(q['selected_N'] for q in results), old_exposure_unique_incoming=len(old),
        pilot_unique_incoming=len(set(allkeys)), requested_bytes=sum(q['resources']['requested_bytes'] for q in results),
        worker_CPU_s=sum(q['resources']['CPU_s'] for q in results), wall_s=time.perf_counter()-tick,
        parent_identity='Uncertified GENIE parent; exact incoming proxy only, not blind certification',
        counts_scope='Existing PHY producer views. Not original merge selection; no training on incompatible views.',
        GPU=0, fits=0, forwards=0)
    assert result['requested_bytes'] < p['resources']['pilot_read_bytes']
    assert result['worker_CPU_s'] < p['resources']['pilot_CPU_s']
    (OUT/'pilot.json').write_text(json.dumps(result, indent=2)+'\n')
    print({k:v for k,v in result.items() if k!='files'}, flush=True)


if __name__ == '__main__':
    main()
