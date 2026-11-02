#!/usr/bin/env python3
"""Source-batched compact segment extraction, all original development identities."""
import argparse
import json
import resource
import time
import awkward as ak
import numpy as np
import uproot
from segment_information import REPO,CACHE,FIELDS,configuration,matrix,valid_segments,summarize
from calonu_inputs import manifest
from learning_capacity import load_inputs
from local_activity import axes,TRACKS


def extract(index,d,x,names,files,cfg,local_cfg):
    path=CACHE/'shards'/f'{index}.npz';assert not path.exists(),'Do not repeat successful extraction'
    tick,cpu=time.perf_counter(),time.process_time();rows=np.flatnonzero(d['manifest_index']==index)
    columns=['run','eventID','TrackSegments','GhostBustedTrackSegments']+[p+k for p in ['TrackSegment_','GhostBustedTrackSegment_'] for k in FIELDS]+['Track_'+k for k in TRACKS]
    with uproot.open(files[index]['input']) as f:
        t=f['nt'];missing=sorted(set(columns)-set(t.keys()));assert not missing,(index,missing)
        keys=t.arrays(['run','eventID'],library='np');lookup={int(e):i for i,e in enumerate(keys['eventID'])};assert len(lookup)==len(keys['eventID'])
        entries=np.array([lookup[int(e)] for e in d['eventID'][rows]]);np.testing.assert_array_equal(keys['run'][entries],d['run'][rows]);lo,hi=int(entries.min()),int(entries.max())+1
        arr=t.arrays(columns,entry_start=lo,entry_stop=hi)[entries-lo];byte_count=int(f.file.source.num_requested_bytes);raw_entries=t.num_entries
    np.testing.assert_array_equal(ak.to_numpy(arr['eventID']),d['eventID'][rows]);axis,ref,raw,lead=axes(arr,local_cfg)
    np.testing.assert_array_equal(raw['p0']/1000,d['reco_p_GeV'][rows])
    for key,feat in [('x0','ML_mu_x0_mm'),('y0','ML_mu_y0_mm'),('z0','ML_mu_z0_mm')]:np.testing.assert_allclose(raw[key],x[rows,names.index(feat)],rtol=2e-7,atol=1e-5,equal_nan=True)
    np.testing.assert_array_equal(ak.to_numpy(arr['TrackSegments']),x[rows,names.index('TrackSegments')])
    theta=[];conv=[];null=[];counts=[];diagnostics=[];rawcounts=[];rawvalidcounts=[];ghostcounts=[];ghostvalidcounts=[]
    for j,row in enumerate(ak.to_list(arr)):
        eventdiag={};stats=[]
        for prefix,counter in [('TrackSegment_','TrackSegments'),('GhostBustedTrackSegment_','GhostBustedTrackSegments')]:
            assert all(len(row[prefix+k])==row[counter] for k in FIELDS)
            a=matrix(row,prefix);st,valid=valid_segments(a,cfg)
            stats.append((np.bincount(st,minlength=4),np.bincount(st[valid],minlength=4)))
            eventdiag[prefix]=dict(N=len(a),valid_N=int(valid.sum()),ndof0_N=int((a[:,7]==0).sum()),valid_ndof0_N=int(((a[:,7]==0)&valid).sum()),negative_ndof_N=int((a[:,7]<0).sum()),negative_chi2_N=int((a[:,6]<0).sum()),minimum_chi2=float(a[:,6].min()) if len(a) else 0.,nonpositive_pz_N=int((a[:,5]<=0).sum()),nonfinite_N=int((~np.isfinite(a).all(axis=1)).sum()),
                maximum_station_distance_mm=float(abs(a[:,2,None]-np.array(local_cfg['station_centers_mm'])).min(axis=1).max()) if len(a) else 0.,
                maximum_dummy_p_deviation_MeV=float(abs(np.linalg.norm(a[:,3:6],axis=1)-100000).max()) if len(a) else 0.)
        rawcounts.append(stats[0][0]);rawvalidcounts.append(stats[0][1]);ghostcounts.append(stats[1][0]);ghostvalidcounts.append(stats[1][1])
        a=matrix(row,cfg['collection']);v,c,n,ct,detail=summarize(a,axis[j],row['run'],row['eventID'],index,cfg)
        theta.append(v);conv.append(c);null.append(n);counts.append(ct);eventdiag.update(detail)
        # Multiset comparison ignores stored collection ordering, but not repeated rows.
        ra=matrix(row,'TrackSegment_');gb=matrix(row,'GhostBustedTrackSegment_')
        eventdiag['raw_ghost_multiset_identical']=ra.shape==gb.shape and bool(np.array_equal(ra[np.lexsort(ra.T[::-1])],gb[np.lexsort(gb.T[::-1])]))
        diagnostics.append(eventdiag)
    md=dict(stage=51,index=index,events=len(rows),raw_entries=raw_entries,entry_range=[lo,hi],decoded_entries=hi-lo,bytes_read=byte_count,input=files[index]['input'],columns=columns,
        wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        identity_failures=0,F6_total_segments_and_leading_fingerprint_verified=True,nonfirst_leading_N=int((lead!=0).sum()),
        axis_valid_N=np.isfinite(axis).all(axis=2).sum(axis=0).tolist(),
        collections={p:dict(segments_N=sum(e[p]['N'] for e in diagnostics),valid_N=sum(e[p]['valid_N'] for e in diagnostics),ndof0_N=sum(e[p]['ndof0_N'] for e in diagnostics),
            valid_ndof0_N=sum(e[p]['valid_ndof0_N'] for e in diagnostics),negative_ndof_N=sum(e[p]['negative_ndof_N'] for e in diagnostics),negative_chi2_N=sum(e[p]['negative_chi2_N'] for e in diagnostics),nonpositive_pz_N=sum(e[p]['nonpositive_pz_N'] for e in diagnostics),nonfinite_N=sum(e[p]['nonfinite_N'] for e in diagnostics),
            minimum_chi2=min(e[p]['minimum_chi2'] for e in diagnostics),maximum_station_distance_mm=max(e[p]['maximum_station_distance_mm'] for e in diagnostics),maximum_dummy_p_deviation_MeV=max(e[p]['maximum_dummy_p_deviation_MeV'] for e in diagnostics)) for p in ['TrackSegment_','GhostBustedTrackSegment_']},
        raw_ghost_multiset_identical_N=sum(e['raw_ghost_multiset_identical'] for e in diagnostics),
        exact_duplicate_N=sum(e['exact_duplicate_N'] for e in diagnostics),shuffled_pairings_N=sum(e['shuffled_pairings_N'] for e in diagnostics))
    path.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path,cache_row=rows,run=d['run'][rows],eventID=d['eventID'][rows],angles=np.stack(theta),convergence=np.stack(conv),shuffle=np.stack(null),
        valid_unique_counts=np.stack(counts),raw_counts=np.stack(rawcounts),raw_valid_counts=np.stack(rawvalidcounts),ghost_counts=np.stack(ghostcounts),ghost_valid_counts=np.stack(ghostvalidcounts),
        axis_valid=np.isfinite(axis).all(axis=2),metadata_json=np.array(json.dumps(md)))
    print(json.dumps({k:v for k,v in md.items() if k not in ['columns','collections']}),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--batch',type=int,choices=range(9),required=True);a=p.parse_args();cfg=configuration()
    d,x=load_inputs();files=manifest(REPO);names=json.loads((REPO/'workbook/stage42_energy_ml/preparation.json').read_text())['feature_names'];local_cfg=json.loads((REPO/'ml/configs/local_activity.json').read_text())
    for index in cfg['extraction_batches'][a.batch]:extract(index,d,x,names,files,cfg,local_cfg)


if __name__=='__main__':main()
