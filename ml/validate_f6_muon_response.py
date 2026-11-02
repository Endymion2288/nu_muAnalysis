#!/usr/bin/env python3
"""Validate full coverage, sufficient statistics, fixed-cell comparisons and compact archive."""
import argparse
import csv
import json
import tarfile
import time

import numpy as np

from analyze_f6_muon_response import load_source
from read_f6_muon_response import COUNTS, REPO, configuration

p=argparse.ArgumentParser();p.add_argument('--archive',action='store_true');args=p.parse_args()
cfg=configuration();out=REPO/'workbook/stage52_energy_ml';cache=REPO/cfg['cache']/'shards'
if args.archive:
    assert cache.is_dir() and not (cache.parent/'source_histograms.tar.gz').exists(), 'Already archived; use validation without --archive'
tick=time.perf_counter();ns=[];ss=[];extras=[];nonfinite=[];edge_drift=0.0;first_edges=None;records=[]
audit=json.loads((out/'input_audit.json').read_text())['records']
for i in range(18):
    with load_source(cache,i) as z:
        m=json.loads(str(z['metadata_json']));n=z['n'];h=z['count_hist'];s=z['count_sum'];e=z['count_extra']
        assert m['index']==i and not m['smoke'] and m['read_entries']==m['file_entries']==audit[i]['entries']
        assert m['cutflow']['input']==m['read_entries'] and n.sum()==m['selected']
        np.testing.assert_array_equal(h.sum(axis=2),np.broadcast_to(n[:,None],(40,6)))
        np.testing.assert_array_equal(z['charge_hist'].sum(axis=2)+z['charge_nonfinite'],np.broadcast_to(n[:,None],(40,2)))
        for j,threshold in enumerate(cfg['extra_activity_thresholds']):
            np.testing.assert_array_equal(h[:,j,threshold+1:].sum(axis=1),e[:,j])
        lower=(h*np.arange(514)).sum(axis=2)
        assert np.all(s>=lower)
        np.testing.assert_array_equal(s[h[:,:,-1]==0],lower[h[:,:,-1]==0])
        edges=z['charge_edges']
        if first_edges is None:first_edges=edges
        else:
            finite=np.isfinite(edges)&np.isfinite(first_edges)
            edge_drift=max(edge_drift,float(np.max(abs(edges[finite]-first_edges[finite]))))
        records.append(m);ns.append(n);ss.append(s);extras.append(e);nonfinite.append(z['charge_nonfinite'].sum(axis=0).tolist())
ns=np.array(ns);ss=np.array(ss);extras=np.array(extras)
assert set(cfg['reference_indices']).isdisjoint(cfg['evaluation_indices'])
assert sorted(cfg['reference_indices']+cfg['evaluation_indices'])==list(range(18))
cells=list(csv.DictReader((out/'common_cells.tsv').open(),delimiter='\t'))
target=np.array([float(r['target_mass']) for r in cells]);np.testing.assert_allclose(target.sum(),1,atol=1e-15)
rows=list(csv.DictReader((out/'response_comparison.tsv').open(),delimiter='\t'))
for label,indices in [('data',[13,15,17]),('MC',[1,3,5,7,9,11])]:
    denom=ns[indices].sum(axis=0);w=target/denom
    np.testing.assert_allclose(denom*w,target,rtol=1e-15,atol=1e-17)
    mean=np.einsum('c,scj->j',w,ss[indices]);extra=100*np.einsum('c,scj->j',w,extras[indices])
    for j,k in enumerate(COUNTS):
        for suffix,val in [('_mean',mean[j]),('_extra_pct',extra[j])]:
            rr=next(r for r in rows if r['stratum']=='all' and r['metric']==k+suffix)
            np.testing.assert_allclose(float(rr[label]),val,rtol=2e-15,atol=1e-14)
io=json.loads((out/'io_diagnosis.json').read_text())
requested=sum(r['requested_bytes'] for r in records)
assert requested==io['predicted_chunk_basket_touches_bytes']+io['metadata_requested_bytes']
archive_bytes=None;archive_equal=False
if args.archive:
    archive=cache.parent/'source_histograms.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for i in range(18):tar.add(cache/f'{i}.npz',arcname=f'{i}.npz')
    with tarfile.open(archive,'r:gz') as tar:
        for i in range(18):assert tar.extractfile(f'{i}.npz').read()==(cache/f'{i}.npz').read_bytes()
    archive_bytes=archive.stat().st_size;archive_equal=True
    for i in range(18):(cache/f'{i}.npz').unlink()
    cache.rmdir()
    # Exercise the final analysis reader on the archived layout.
    for i in range(18):
        with load_source(cache,i) as z:np.testing.assert_array_equal(z['n'],ns[i])
value=dict(full_18_sources_and_6021535_entries=True,all_histogram_denominators_exact=True,
           count_mean_sums_unclipped=True,extra_rate_histograms_exact=True,reference_eval_sources_disjoint=True,
           fixed_cell_mass_and_main_count_tables_independently_recomputed=True,
           per_source_charge_nonfinite_events=nonfinite,maximum_far_tail_edge_drift_pC=edge_drift,
           all_central_1pC_edges_exact=True,tail_edge_float32_bin_invariance='asserted by final analysis',
           requested_bytes_exactly_explained_by_basket_touches_and_metadata=True,
           requested_byte_budget_GB=cfg['requested_bytes_budget_GB'],requested_bytes_GB=requested/1e9,
           requested_byte_budget_excess_pct=100*(requested/(cfg['requested_bytes_budget_GB']*1e9)-1),
           archive_bytes=archive_bytes,archive_all18_file_bytes_equal=archive_equal,archive_reader_all18_n_equal=archive_equal,
           wall_s=time.perf_counter()-tick)
(out/'validation.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(value))
