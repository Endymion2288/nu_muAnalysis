#!/usr/bin/env python3
"""Stream full known muon files into per-source, per-cell sufficient histograms."""
import argparse
import json
import resource
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

from calonu_muon_control import manifest

REPO = Path(__file__).resolve().parents[1]
COUNTS = ['nClusters0','nClusters1','nClusters2','nClusters3','SpacePoints','TrackSegments']
TRACKS = ['p0','pz0','nLayers','nDoF','Chi2','charge','X_atVetoNu','Y_atVetoNu',
          'ThetaX_atVetoNu','ThetaY_atVetoNu','X_atTrig','Y_atTrig']
VETO = ['VetoNu0','VetoNu1','Veto20','Veto21']
TIMING = [f'Timing{i}' for i in range(4)]
NCELLS = 40
CHARGE_EDGES = np.r_[-np.inf, np.arange(-128,8193,dtype=float), np.geomspace(8193,1e6,81), np.inf]


def configuration():
    return json.loads((REPO/'ml/configs/f6_muon_response.json').read_text())


def branches():
    return (['run','eventID','eventTime','distanceToCollidingBCID','longTracks','TBP','TAP','inputBits']
            + COUNTS + ['Track_'+k for k in TRACKS] + [k+'_raw_charge' for k in VETO]
            + [k+'_'+v for k in TIMING for v in ['charge','raw_charge','status']])


def select(arr, sample, grl, cfg, include_mask=False):
    idx = ak.argmax(arr['Track_pz0'],axis=1,keepdims=True)
    lengths = ak.num(arr['Track_pz0'])
    v = {}
    for k in branches():
        if k.startswith('Track_'):
            assert bool(ak.all(ak.num(arr[k]) == lengths)), k
            v[k] = ak.to_numpy(ak.fill_none(ak.firsts(arr[k][idx]),np.nan))
        else:
            v[k] = ak.to_numpy(arr[k])
    stable = np.ones(len(arr),bool)
    if sample == 'data':
        stable[:] = False
        for run in np.unique(v['run']):
            r = grl[str(int(run))]
            good = np.zeros(len(arr),bool)
            for interval in r['stable_list']:
                good |= (v['eventTime'] >= interval['start_utime']) & (v['eventTime'] <= interval['stop_utime'])
            for interval in r.get('excluded_list',[]):
                good &= ~((v['eventTime'] >= interval['start_utime']) & (v['eventTime'] <= interval['stop_utime']))
            stable |= (v['run'] == run) & good
        stable &= v['distanceToCollidingBCID'] == 0
    with np.errstate(divide='ignore',invalid='ignore'):
        quality = (v['Track_nLayers']>=7)&(v['Track_nDoF']>=9)&(v['Track_Chi2']/v['Track_nDoF']<15)
    cuts = [('stable_colliding_if_data',stable),('one_long_track',v['longTracks']==1),('track_quality',quality),
            ('reco_p_100_1000_GeV',(v['Track_p0']>=100000)&(v['Track_p0']<1000000)),
            ('valid_vetonu_extrapolation',(abs(v['Track_X_atVetoNu'])<500)&(abs(v['Track_Y_atVetoNu'])<500)
             &(np.hypot(v['Track_ThetaX_atVetoNu'],v['Track_ThetaY_atVetoNu'])<.025)),
            ('four_veto_tag',np.logical_and.reduce([v[k+'_raw_charge']>40 for k in VETO])),
            ('central_timing_plane',(abs(v['Track_X_atTrig'])<80)&(abs(v['Track_Y_atTrig'])<80)),
            ('unit_reco_charge',abs(v['Track_charge'])==1)]
    keep = np.ones(len(arr),bool)
    flow = {'input':len(arr)}
    for name, cut in cuts:
        keep &= cut
        flow[name] = int(keep.sum())
    selected = {k:x[keep] for k,x in v.items()}
    return (selected, flow, keep) if include_mask else (selected, flow)


def cells(v,cfg):
    p = v['Track_p0']/1000
    a = np.searchsorted(cfg['p_edges_GeV'],p,side='right')-1
    x = (v['Track_X_atTrig']>=0).astype(int)
    y = (v['Track_Y_atTrig']>=0).astype(int)
    q = (v['Track_charge']>0).astype(int)
    return (((a*2+x)*2+y)*2+q).astype(int)


def extract(index, output, smoke=False):
    cfg=configuration();row=manifest(REPO)[index]
    grl=json.loads((REPO/cfg['grl']).read_text())
    tick,cpu=time.perf_counter(),time.process_time()
    n=np.zeros(NCELLS,np.int64)
    sums=np.zeros((NCELLS,6));extra=np.zeros((NCELLS,6),np.int64)
    count_hist=np.zeros((NCELLS,6,514),np.int64)
    charge_hist=np.zeros((NCELLS,2,len(CHARGE_EDGES)-1),np.int64)
    nonfinite=np.zeros((NCELLS,2),np.int64)
    flags=np.zeros((NCELLS,5),np.int64)
    kin=np.zeros((NCELLS,3));kin2=np.zeros((NCELLS,3))
    flow={};patterns={k:{} for k in ['TBP','TAP','inputBits']}
    identity_entries=0;maxima=np.zeros(6,np.int64);minima=np.full(6,np.iinfo(np.int64).max)
    with uproot.open(row['input']) as f:
        t=f['nt'];total=t.num_entries
        stop=min(total, {0:10,6:10,12:5,14:5,16:10}[index]) if smoke else total
        for start in range(0,stop,cfg['chunk_entries']):
            arr=t.arrays(branches(),entry_start=start,entry_stop=min(start+cfg['chunk_entries'],stop))
            assert bool(ak.all(arr['run']==int(row['run'])))
            v,cut=select(arr,row['sample'],grl,cfg)
            for k,val in cut.items():flow[k]=flow.get(k,0)+val
            m=len(v['run']);identity_entries+=m
            if not m:continue
            cell=cells(v,cfg);assert np.all((cell>=0)&(cell<NCELLS))
            n+=np.bincount(cell,minlength=NCELLS)
            for k in patterns:
                vals,num=np.unique(v[k],return_counts=True)
                for val,nn in zip(vals,num):patterns[k][str(int(val))]=patterns[k].get(str(int(val)),0)+int(nn)
            for j,k in enumerate(COUNTS):
                val=v[k].astype(np.int64);assert np.all(val>=0)
                maxima[j]=max(maxima[j],val.max());minima[j]=min(minima[j],val.min())
                sums[:,j]+=np.bincount(cell,weights=val,minlength=NCELLS)
                extra[:,j]+=np.bincount(cell,weights=(val>cfg['extra_activity_thresholds'][j]),minlength=NCELLS).astype(np.int64)
                count_hist[:,j,:]+=np.bincount(cell*514+np.minimum(val,513),minlength=NCELLS*514).reshape(NCELLS,514)
            qs=np.array([[v[k+'_'+kind] for k in TIMING] for kind in ['charge','raw_charge']]).sum(axis=1)
            for j,val in enumerate(qs):
                finite=np.isfinite(val)
                nonfinite[:,j]+=np.bincount(cell[~finite],minlength=NCELLS)
                bins=np.searchsorted(CHARGE_EDGES,val[finite],side='right')-1
                charge_hist[:,j,:]+=np.bincount(cell[finite]*charge_hist.shape[2]+bins,minlength=NCELLS*charge_hist.shape[2]).reshape(NCELLS,-1)
                flags[:,j]+=np.bincount(cell,weights=np.isfinite(val)&(val<=cfg['charge_low_threshold_pC']),minlength=NCELLS).astype(np.int64)
            status=np.array([v[k+'_status'].astype(np.int64) for k in TIMING])
            y=v['Track_Y_atTrig']
            active=np.where(y>20,status[2]|status[3],np.where(y < -20,status[0]|status[1],np.bitwise_or.reduce(status,axis=0)))
            for j,bit in enumerate([1,4,384]):
                flags[:,j+2]+=np.bincount(cell,weights=(active&bit)!=0,minlength=NCELLS).astype(np.int64)
            for j,val in enumerate([v['Track_p0']/1000,v['Track_X_atTrig'],v['Track_Y_atTrig']]):
                kin[:,j]+=np.bincount(cell,weights=val,minlength=NCELLS)
                kin2[:,j]+=np.bincount(cell,weights=val*val,minlength=NCELLS)
        requested_bytes=int(f.file.source.num_requested_bytes)
    assert n.sum()==identity_entries==flow['unit_reco_charge']
    assert np.all(count_hist.sum(axis=2)==n[:,None])
    assert np.all(charge_hist.sum(axis=2)+nonfinite==n[:,None])
    meta=dict(index=index,sample=row['sample'],run=int(row['run']),group=row['group'],input=row['input'],file_entries=total,
              read_entries=stop,selected=int(n.sum()),cutflow=flow,trigger_patterns=patterns,source_entry_identity='stream every original entry once; PG eventID collisions not deduplicated',
              leading='highest pz; all Track vectors aligned',minimum_counts=minima.tolist(),maximum_counts=maxima.tolist(),requested_bytes=requested_bytes,
              wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
              frozen_utc=cfg['frozen_utc'],smoke=smoke)
    output.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(output,n=n,count_sum=sums,count_extra=extra,count_hist=count_hist,charge_hist=charge_hist,
                        charge_nonfinite=nonfinite,flags=flags,kin_sum=kin,kin_sum2=kin2,charge_edges=CHARGE_EDGES,metadata_json=np.array(json.dumps(meta)))
    print(json.dumps(meta),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index',type=int,required=True);p.add_argument('--smoke',action='store_true');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();extract(a.index,a.output,a.smoke)


if __name__=='__main__':main()
