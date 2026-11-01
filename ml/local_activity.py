#!/usr/bin/env python3
"""Frozen short-range leading-muon / SpacePoint summaries and conditional null."""
import argparse
import json
import resource
import time
from pathlib import Path
import awkward as ak
import numpy as np
import uproot
from calonu_inputs import manifest, feature_names

REPO = Path(__file__).resolve().parents[1]
TRACKS = ['p0','pz0','x0','y0','z0','x1','y1','z1','px1','py1','pz1'] + [
    k+'_'+plane for plane in ['atVetoStation1','atTrig'] for k in ['X','Y','ThetaX','ThetaY']]


def axes(arr, cfg):
    lengths = ak.num(arr['Track_pz0'])
    for n in TRACKS: assert bool(ak.all(ak.num(arr['Track_'+n]) == lengths)), n
    assert bool(ak.all(lengths > 0))
    lead = ak.argmax(arr['Track_pz0'], axis=1, keepdims=True)
    raw = {n: ak.to_numpy(ak.flatten(arr['Track_'+n][lead])).astype(float) for n in TRACKS}
    for v in raw.values(): v[(v == 999999) | ~np.isfinite(v)] = np.nan
    result = np.full((len(arr), 3, 4), np.nan)
    refz = np.full((len(arr), 3), np.nan)
    for j, (station, plane, zref) in enumerate([(0,'atVetoStation1',-1769.65),(1,'atTrig',0),(3,None,None)]):
        if plane:
            x, y = raw['X_'+plane], raw['Y_'+plane]
            sx, sy = np.tan(raw['ThetaX_'+plane]), np.tan(raw['ThetaY_'+plane])
            zr = np.full(len(arr), zref)
        else:
            x, y, zr = raw['x1'], raw['y1'], raw['z1']
            with np.errstate(divide='ignore', invalid='ignore'):
                sx, sy = raw['px1']/raw['pz1'], raw['py1']/raw['pz1']
        dz = cfg['station_centers_mm'][station]-zr
        values = np.column_stack([x+sx*dz,y+sy*dz,sx,sy])
        # Include the full +/-38mm station envelope, also when a station has no points.
        good = np.isfinite(values).all(axis=1) & np.isfinite(zr) & (abs(dz)+38 <= cfg['maximum_local_dz_mm'])
        result[good,j] = values[good]; refz[good,j] = zr[good]
    return result, refz, raw, ak.to_numpy(ak.flatten(lead))


def summary(points, ax, cfg):
    x,y,z = points.T
    finitez = np.isfinite(z)
    distance = np.abs(z[:,None]-np.array(cfg['station_centers_mm']))
    station = np.argmin(np.where(np.isfinite(distance),distance,np.inf),axis=1)
    counts = np.bincount(station[finitez],minlength=4).astype(float)
    values = list(counts)
    for j,s in enumerate(cfg['local_stations']):
        valid = np.isfinite(ax[j]).all()
        if not valid: values += [np.nan]*5+[0.]; continue
        take = (station == s)&finitez&np.isfinite(x)&np.isfinite(y)
        a,b,sx,sy = ax[j]; dz = z[take]-cfg['station_centers_mm'][s]
        dx,dy = x[take]-a-sx*dz,y[take]-b-sy*dz
        radius = np.hypot(dx,dy); out = radius > cfg['radii_mm'][0]
        values += [float(out.sum()),float((radius > cfg['radii_mm'][1]).sum()),
                   float(dx[out].mean()) if out.any() else np.nan,float(dy[out].mean()) if out.any() else np.nan,
                   float(np.sqrt(np.mean(radius[out]**2))) if out.any() else np.nan,1.]
    return np.array(values,dtype='float32')


def donors(d, ax, cfg):
    n=len(ax); result=np.arange(n); rng=np.random.default_rng(cfg['null_seed'])
    edges=[float(v) for v in cfg['null_p_edges_GeV']]
    pbin=np.searchsorted(edges,d['reco_p_GeV'],side='right')-1
    valid=np.isfinite(ax).all(axis=2); pattern=valid@np.array([1,2,4])
    pools=[]
    for group in np.unique(d['group']):
        for p in np.unique(pbin):
            for pat in np.unique(pattern):
                ids=np.flatnonzero((d['group']==group)&(pbin==p)&(pattern==pat))
                if not len(ids): continue
                order=rng.permutation(ids); result[order]=np.roll(order,1)
                pools.append(dict(group=str(group),pbin=int(p),valid_pattern=int(pat),N=len(ids)))
    assert (d['group'][result]==d['group']).all() and (d['fold'][result]==d['fold']).all()
    assert (pbin[result]==pbin).all() and (pattern[result]==pattern).all()
    for pool in pools:
        ids=np.flatnonzero((d['group']==pool['group'])&(pbin==pool['pbin'])&(pattern==pool['valid_pattern']))
        if pool['N']>1: assert (result[ids]!=ids).all()
    return result,pools


def main():
    p=argparse.ArgumentParser();p.add_argument('--pilot-json');a=p.parse_args()
    cfg=json.loads((REPO/'ml/configs/local_activity.json').read_text())
    if a.pilot_json:
        arr=ak.Array(json.loads(Path(a.pilot_json).read_text())); ax,rz,raw,lead=axes(arr,cfg)
        v=np.stack([summary(np.column_stack([np.array(row['SpacePoint_'+k]) for k in 'xyz']),ax[i],cfg) for i,row in enumerate(ak.to_list(arr))])
        out=REPO/'ntuples/energy_ml_stage44';out.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(out/'pilot.npz',local=v,axes=ax,run=ak.to_numpy(arr['run']),eventID=ak.to_numpy(arr['eventID']))
        pilot_d=dict(group=np.array(['pilot']*len(v)),fold=np.zeros(len(v),int),reco_p_GeV=raw['p0']/1000)
        donor,pools=donors(pilot_d,ax,cfg)
        nv=np.stack([summary(np.column_stack([np.array(row['SpacePoint_'+k]) for k in 'xyz']),ax[donor[i]],cfg) for i,row in enumerate(ak.to_list(arr))])
        np.testing.assert_array_equal(v[:,:4],nv[:,:4]);np.testing.assert_array_equal(v[:,[9,15,21]],nv[:,[9,15,21]])
        (REPO/'workbook/stage44_energy_ml/reco_smoke.json').write_text(json.dumps(dict(events=len(v),features=22,counts_and_missing_preserved=True,donor=donor.tolist(),pools=pools),indent=2)+'\n')
        print(json.dumps(dict(pilot_events=len(v),features=v.shape[1],all_axes_valid=bool(np.isfinite(ax).all()),station_counts=v[:,:4].tolist())));return
    tick,cpu=time.perf_counter(),time.process_time()
    with np.load(REPO/'ntuples/energy_ml_stage42/development.npz') as z:
        chosen=np.flatnonzero(z['selected']); d={k:z[k][chosen] for k in z.files}
    assert len(chosen)<=cfg['max_events']
    files=manifest(REPO); ax=np.full((len(chosen),3,4),np.nan); refz=np.full((len(chosen),3),np.nan)
    seen=np.zeros(len(chosen),int); source_resources=[]; lead_nonzero=0
    base_names,extra_names=feature_names(REPO); names=base_names+extra_names
    assert d['x'].shape[1]==len(names)==65
    # First inexpensive pass obtains every axis, allowing source-local donor matching before point extraction.
    for index in cfg['indices']:
        start=time.perf_counter(); wanted=np.flatnonzero(d['manifest_index']==index)
        lookup={int(d['eventID'][i]):i for i in wanted}
        with uproot.open(files[index]['input']) as f:
            for arr in f['nt'].iterate(['run','eventID']+['Track_'+n for n in TRACKS],step_size='16 MB'):
                ids=ak.to_numpy(arr['eventID']); take=np.array([int(e) in lookup for e in ids]); arr=arr[take]
                if not len(arr):continue
                positions=np.array([lookup[int(e)] for e in ak.to_numpy(arr['eventID'])]); seen[positions]+=1
                np.testing.assert_array_equal(ak.to_numpy(arr['run']),d['run'][positions])
                values,zr,raw,lead=axes(arr,cfg); ax[positions]=values; refz[positions]=zr;lead_nonzero+=int((lead!=0).sum())
                np.testing.assert_array_equal(raw['p0']/1000,d['reco_p_GeV'][positions])
                for key,feat in [('x0','ML_mu_x0_mm'),('y0','ML_mu_y0_mm'),('z0','ML_mu_z0_mm')]:
                    np.testing.assert_allclose(raw[key],d['x'][positions,names.index(feat)],rtol=2e-7,atol=1e-5,equal_nan=True)
        source_resources.append(dict(manifest_index=index,axis_pass_wall_s=time.perf_counter()-start,N=len(wanted)))
    assert (seen==1).all(); donor,pools=donors(d,ax,cfg)
    actual=np.full((len(chosen),22),np.nan,dtype='float32'); null=actual.copy(); seen[:]=0
    max_layer=0.;nonfinite_points=0;total_points=0;total_raw=0;max_dz=np.zeros(3); nearest=[[],[],[]]
    for index in cfg['indices']:
        start=time.perf_counter();wanted=np.flatnonzero(d['manifest_index']==index);lookup={int(d['eventID'][i]):i for i in wanted}
        with uproot.open(files[index]['input']) as f:
            total_raw+=f['nt'].num_entries
            for arr in f['nt'].iterate(['run','eventID','SpacePoints','SpacePoint_x','SpacePoint_y','SpacePoint_z'],step_size='32 MB'):
                take=np.array([int(e) in lookup for e in ak.to_numpy(arr['eventID'])]); arr=arr[take]
                for row in ak.to_list(arr):
                    i=lookup[int(row['eventID'])];seen[i]+=1;assert row['run']==d['run'][i]
                    points=np.column_stack([row['SpacePoint_'+k] for k in 'xyz']).astype(float)
                    assert len(points)==row['SpacePoints'];total_points+=len(points);nonfinite_points+=int((~np.isfinite(points).all(axis=1)).sum())
                    z=points[:,2];good=np.isfinite(z);distance=np.abs(z[:,None]-np.array(cfg['station_centers_mm']));st=np.argmin(np.where(np.isfinite(distance),distance,np.inf),axis=1)
                    layer_dist=np.min(np.abs(z[good,None]-np.array(cfg['station_centers_mm'])[st[good],None]-np.array(cfg['layer_offsets_mm'])),axis=1)
                    if len(layer_dist):max_layer=max(max_layer,float(layer_dist.max()));assert (layer_dist<=cfg['layer_tolerance_mm']).all()
                    for j,s in enumerate(cfg['local_stations']):
                        if not np.isfinite(ax[i,j]).all():continue
                        take=(st==s)&good
                        if take.any():
                            dz=float(np.max(abs(z[take]-refz[i,j])));max_dz[j]=max(max_dz[j],dz);assert dz<=cfg['maximum_local_dz_mm']
                            v=ax[i,j];delta=points[take,:2]-v[:2]-(z[take,None]-cfg['station_centers_mm'][s])*v[2:]
                            radius=np.linalg.norm(delta,axis=1);radius=radius[np.isfinite(radius)]
                            if len(radius):nearest[j].append(float(radius.min()))
                    actual[i]=summary(points,ax[i],cfg);null[i]=summary(points,ax[donor[i]],cfg)
                    assert actual[i,:4].sum()==row['SpacePoints']-int((~good).sum())
        rec=next(r for r in source_resources if r['manifest_index']==index);rec['point_pass_wall_s']=time.perf_counter()-start
        print(json.dumps(rec),flush=True)
    assert (seen==1).all();np.testing.assert_array_equal(actual[:,:4],null[:,:4]);np.testing.assert_array_equal(actual[:,[9,15,21]],null[:,[9,15,21]])
    np.testing.assert_array_equal(actual[:,:4].sum(axis=1),d['x'][:,names.index('SpacePoints')])
    out=REPO/'ntuples/energy_ml_stage44';out.mkdir(parents=True,exist_ok=True)
    meta=dict(config=cfg,events=len(chosen),sources=len(cfg['indices']),raw_entries=total_raw,selected_points=total_points,nonfinite_points=nonfinite_points,
              maximum_layer_distance_mm=max_layer,maximum_local_dz_mm=max_dz.tolist(),axis_valid_N=np.isfinite(ax).all(axis=2).sum(axis=0).tolist(),
              nearest_point_distance_mm_quantiles=[np.quantile(v,[0,.5,.95,1]).tolist() if len(v) else [] for v in nearest],
              singleton_self_N=int((donor==np.arange(len(donor))).sum()),donor_pools=pools,nonfirst_leading_N=lead_nonzero,source_resources=source_resources,
              wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    np.savez_compressed(out/'features.npz',cache_row=chosen,run=d['run'],eventID=d['eventID'],counts=actual[:,:4],local=actual,null=null,axes=ax,donor_row=donor,metadata_json=np.array(json.dumps(meta)))
    (out/'extraction.json').write_text(json.dumps(meta,indent=2)+'\n'); print(json.dumps({k:v for k,v in meta.items() if k not in ['config','donor_pools','source_resources']}))


if __name__=='__main__':main()
