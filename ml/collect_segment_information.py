#!/usr/bin/env python3
"""Join all 81 source shards and audit unchanged control marginals and full support."""
import json
import numpy as np
from segment_information import REPO,OUT,CACHE,configuration,feature_names
from learning_capacity import load_inputs
from train_bdt import write_table

cfg=configuration();d,x=load_inputs();parts=[];records=[]
for index in cfg['indices']:
    with np.load(CACHE/'shards'/f'{index}.npz') as z:p={k:z[k] for k in z.files}
    md=json.loads(str(p.pop('metadata_json')));assert md['stage']==51 and md['index']==index and md['identity_failures']==0
    rows=p['cache_row'];np.testing.assert_array_equal(rows,np.flatnonzero(d['manifest_index']==index))
    for key in ['run','eventID']:np.testing.assert_array_equal(p[key],d[key][rows])
    parts.append(p);records.append(md)
order=np.argsort(np.concatenate([p['cache_row'] for p in parts]));joined={k:np.concatenate([p[k] for p in parts])[order] for k in parts[0]}
np.testing.assert_array_equal(joined['cache_row'],np.arange(len(x)));assert joined['angles'].shape==(14309,46) and joined['convergence'].shape==(14309,24)
np.testing.assert_array_equal(np.isnan(joined['convergence']),np.isnan(joined['shuffle']))
np.testing.assert_array_equal(joined['convergence'][:,2::6],joined['shuffle'][:,2::6])
counts=joined['valid_unique_counts'];source=[]
for i,r in zip(cfg['indices'],records):
    m=d['manifest_index']==i
    source.append(dict(index=i,group=str(d['group'][m][0]),events=int(m.sum()),bytes_read=r['bytes_read'],wall_s=r['wall_s'],cpu_s=r['cpu_s'],peak_rss_MiB=r['peak_rss_MiB'],
        raw_station_segments=joined['raw_counts'][m].sum(axis=0).tolist(),ghost_station_segments=joined['ghost_counts'][m].sum(axis=0).tolist(),valid_unique_station_segments=counts[m].sum(axis=0).tolist(),
        station_nonempty_event_N=(counts[m]>0).sum(axis=0).tolist(),station_multipair_event_N=(counts[m]>=2).sum(axis=0).tolist(),**{k:r[k] for k in ['exact_duplicate_N','shuffled_pairings_N','raw_ghost_multiset_identical_N']}))
write_table(OUT/'source_coverage.tsv',source)
support=[];focus=(d['reco_p_GeV']>=100)&(d['reco_p_GeV']<1000)
from report_calonu_information import strata
for support_name,mask in [('A_full',np.ones(len(x),bool)),('A_B_sources',d['selected']),('A_remaining_sources',~d['selected'])]:
    for label,layer in strata(d).items():
        take=mask&layer
        if not take.any():continue
        support.append(dict(support=support_name,stratum=label,N=int(take.sum()),sources=len(set(d['group'][take])),
            raw_station_segments=joined['raw_counts'][take].sum(axis=0).tolist(),valid_unique_station_segments=counts[take].sum(axis=0).tolist(),
            station_nonempty_event_N=(counts[take]>0).sum(axis=0).tolist(),station_multipair_event_N=(counts[take]>=2).sum(axis=0).tolist(),
            angle_any_N=int(np.isfinite(joined['angles'][take]).any(axis=1).sum()),local_convergence_any_N=int((counts[take]>=2).any(axis=1).sum()),
            mu_axis_valid_N=joined['axis_valid'][take].sum(axis=0).tolist()))
write_table(OUT/'coverage.tsv',support)
bytes_read=sum(r['bytes_read'] for r in records);assert bytes_read<=cfg['formal_extraction_total_bytes_limit']
md=dict(events=len(x),sources=len(records),all_events_seen_once=True,identity_failures=0,bytes_read=bytes_read,
    wall_sum_s=sum(r['wall_s'] for r in records),cpu_sum_s=sum(r['cpu_s'] for r in records),peak_rss_MiB=max(r['peak_rss_MiB'] for r in records),
    angle_features=46,convergence_features=24,angle_finite_N=np.isfinite(joined['angles']).sum(axis=0).tolist(),convergence_finite_N=np.isfinite(joined['convergence']).sum(axis=0).tolist(),
    raw_segments_N=int(joined['raw_counts'].sum()),ghost_segments_N=int(joined['ghost_counts'].sum()),valid_unique_segments_N=int(counts.sum()),
    raw_ghost_multiset_identical_N=sum(r['raw_ghost_multiset_identical_N'] for r in records),exact_duplicate_N=sum(r['exact_duplicate_N'] for r in records),
    shuffled_pairings_N=sum(r['shuffled_pairings_N'] for r in records),
    collections={p:{k:sum(r['collections'][p][k] for r in records) for k in ['segments_N','valid_N','ndof0_N','valid_ndof0_N','negative_ndof_N','negative_chi2_N','nonpositive_pz_N','nonfinite_N']} for p in ['TrackSegment_','GhostBustedTrackSegment_']},
    collection_minimum_chi2={p:min(r['collections'][p]['minimum_chi2'] for r in records) for p in ['TrackSegment_','GhostBustedTrackSegment_']},
    collection_maxima={p:{k:max(r['collections'][p][k] for r in records) for k in ['maximum_station_distance_mm','maximum_dummy_p_deviation_MeV']} for p in ['TrackSegment_','GhostBustedTrackSegment_']},
    missing_and_center_dispersion_preserved=True,columns=records[0]['columns'],extraction_records=[{k:v for k,v in r.items() if k!='columns'} for r in records])
assert all(r['columns']==records[0]['columns'] for r in records)
np.savez_compressed(CACHE/'features.npz',**joined)
(OUT/'extraction.json').write_text(json.dumps(md,indent=2)+'\n')
print(json.dumps({k:v for k,v in md.items() if k not in ['extraction_records','angle_finite_N','convergence_finite_N']}))
