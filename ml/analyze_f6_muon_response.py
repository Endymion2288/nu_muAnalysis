#!/usr/bin/env python3
"""Fixed-cell, source-separated F6 muon activity/Timing response control."""
import csv
import io
import tarfile
import json
import resource
import time
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from read_f6_muon_response import REPO, COUNTS, configuration

OUT=REPO/'workbook/stage52_energy_ml'


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def write_tsv(path,rows):
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows({k:('NA' if v is None else v) for k,v in row.items()} for row in rows)


def quantiles(hist,edges):
    c=np.cumsum(hist);total=c[-1]
    if not total:return [None]*3
    idx=np.searchsorted(c,np.array([.16,.5,.84])*total)
    lo,hi=edges[idx],edges[idx+1]
    # Nonfinite endpoints are bounded to nearest finite edge; flag these separately.
    val=np.where(np.isfinite(lo)&np.isfinite(hi),(lo+hi)/2,np.where(np.isfinite(lo),lo,hi))
    return val.tolist()


def load_source(cache, index):
    if cache.is_dir():
        return np.load(cache/f'{index}.npz')
    with tarfile.open(cache.parent/'source_histograms.tar.gz','r:gz') as tar:
        return np.load(io.BytesIO(tar.extractfile(f'{index}.npz').read()))


def main():
    cfg=configuration();tick,cpu=time.perf_counter(),time.process_time()
    cache=REPO/cfg['cache']/'shards'
    records=[];data={};edges=None
    fields=['n','count_sum','count_extra','count_hist','charge_hist','charge_nonfinite','flags','kin_sum','kin_sum2']
    for i in range(18):
        with load_source(cache, i) as z:
            m=json.loads(str(z['metadata_json']));assert m['index']==i and not m['smoke']
            assert m['read_entries']==m['file_entries'] and m['frozen_utc']==cfg['frozen_utc']
            records.append(m)
            for k in fields:data.setdefault(k,[]).append(z[k])
            if edges is None:edges=z['charge_edges']
            else:
                other=z['charge_edges']
                # CPU libm differs by <=a few ULPs in geometric far-tail edges.
                # All central 1pC edges must be exact; any differing edge must
                # contain no representable float32 charge sum between versions.
                np.testing.assert_array_equal(edges[:8322],other[:8322])
                np.testing.assert_allclose(edges,other,rtol=5e-15,atol=0)
                diff=(edges!=other)&np.isfinite(edges)&np.isfinite(other)
                low=np.minimum(edges[diff],other[diff]);high=np.maximum(edges[diff],other[diff])
                ceil=low.astype(np.float32)
                ceil=np.where(ceil.astype(float)<low,np.nextafter(ceil,np.float32(np.inf)),ceil)
                assert np.all(ceil.astype(float)>high), 'tail edge drift could change a float32 charge bin'
    a={k:np.array(v) for k,v in data.items()};n=a['n'];assert n.sum()==sum(m['selected'] for m in records)
    assert sum(m['read_entries'] for m in records)==cfg['max_input_entries']
    assert np.all(a['count_hist'].sum(axis=3)==n[:,:,None])
    assert np.all(a['charge_hist'].sum(axis=3)+a['charge_nonfinite']==n[:,:,None])
    refD=[12,14,16];refM=[0,2,4,6,8,10];evalD=[13,15,17];evalM=[1,3,5,7,9,11]
    pooledD=n[refD].sum(axis=0);pooledM=n[refM].sum(axis=0)
    mcminus=n[[0,2,4]].sum(axis=0);mcplus=n[[6,8,10]].sum(axis=0)
    applicableMC=np.where(np.arange(40)%2==0,mcminus,mcplus)
    support=(n[refD].min(axis=0)>=20)&(applicableMC>=20)
    target=np.minimum(pooledD/pooledD.sum(),pooledM/pooledM.sum())*support
    assert target.sum()>0
    overlap=target.sum();target/=target.sum()
    cellrows=[]
    for c in range(40):
        ip=c//8;ix=(c//4)%2;iy=(c//2)%2;iq=c%2
        cellrows.append(dict(cell=c,p_lo_GeV=cfg['p_edges_GeV'][ip],p_hi_GeV=cfg['p_edges_GeV'][ip+1],
                             x_lo_mm=cfg['x_edges_mm'][ix],x_hi_mm=cfg['x_edges_mm'][ix+1],
                             y_lo_mm=cfg['y_edges_mm'][iy],y_hi_mm=cfg['y_edges_mm'][iy+1],charge=2*iq-1,
                             support=bool(support[c]),target_mass=float(target[c]),ref_MC=int(pooledM[c]),ref_data=int(pooledD[c]),
                             eval_MC=int(n[evalM,c].sum()),eval_data=int(n[evalD,c].sum())))
    write_tsv(OUT/'common_cells.tsv',cellrows)
    write_json(OUT/'extraction_files.json',records)
    # Stored histograms are sufficient for fixed reference standardization; no per-event cache.
    def weights(ids,t,multiplicity=None):
        ids=np.array(ids);mult=np.ones(len(ids)) if multiplicity is None else np.array(multiplicity)
        denom=(n[ids]*mult[:,None]).sum(axis=0)
        if np.any((t>0)&(denom==0)):return None,None
        percell=np.divide(t,denom,out=np.zeros_like(t),where=denom>0)
        return mult[:,None]*percell[None,:],denom

    def measurement(ids,t,mult=None):
        w,den=weights(ids,t,mult)
        if w is None:return None
        z={k:np.einsum('sc,sc...->...',w,a[k][ids]) for k in ['count_sum','count_extra','count_hist','charge_hist','charge_nonfinite','flags','kin_sum']}
        vals={}
        for j,k in enumerate(COUNTS):
            vals[k+'_mean']=float(z['count_sum'][j])
            vals[k+'_extra_pct']=float(100*z['count_extra'][j])
            # integer hist bin j denotes exact count j, terminal bin is >=513.
            h=z['count_hist'][j];cum=np.cumsum(h)
            vals[k+'_median']=float(np.searchsorted(cum,.5*cum[-1]))
            vals[k+'_q84']=float(np.searchsorted(cum,.84*cum[-1]))
        for j,k in enumerate(['Timing_charge','Timing_raw_charge']):
            q=quantiles(z['charge_hist'][j],edges)
            vals[k+'_median_pC']=q[1]
            vals[k+'_R68_pC']=None if q[0] is None else (q[2]-q[0])/2
            vals[k+'_low_pct']=float(100*z['flags'][j])
            vals[k+'_nonfinite_pct']=float(100*z['charge_nonfinite'][j])
            vals[k+'_hist_under_over_pct']=float(100*(z['charge_hist'][j,0]+z['charge_hist'][j,-1]))
        for j,k in enumerate(['threshold_failed','overflow','missing_invalid']):vals['Timing_active_'+k+'_pct']=float(100*z['flags'][j+2])
        for j,k in enumerate(['p_GeV','x_mm','y_mm']):vals['mean_'+k]=float(z['kin_sum'][j])
        return vals

    def statistics(ids,t):
        w,den=weights(ids,t)
        if w is None:return dict(supported=False,events=int(n[ids].sum()))
        neff=1/np.sum(w*w*n[ids])
        return dict(supported=True,events=int(n[ids].sum()),events_common=int(n[ids][:,t>0].sum()),sources=len(ids),
                    Neff=float(neff),min_cell_N=int(den[t>0].min()),max_event_weight=float(w.max()))

    def normalized_target(mask):
        t=target*mask
        return t/t.sum() if t.sum()>0 else t

    strata={'all':np.ones(40,bool),'p100_250':np.arange(40)//8<2,'p250_1000':np.arange(40)//8>=2}
    for ix in range(2):
        for iy in range(2):strata[f'xy_{ix}_{iy}']=(((np.arange(40)//4)%2)==ix)&(((np.arange(40)//2)%2)==iy)
    for q in [-1,1]:strata[f'charge_{q}']=(np.arange(40)%2==(q+1)//2)
    mainrows=[];summary={};rng=np.random.default_rng(cfg['bootstrap_seed'])
    metric_interval_keys=[k+s for k in COUNTS for s in ['_mean','_extra_pct']]+[
        k+s for k in ['Timing_charge','Timing_raw_charge'] for s in ['_median_pC','_R68_pC','_low_pct']]+[
        'Timing_active_'+k+'_pct' for k in ['threshold_failed','overflow','missing_invalid']]
    mainmeasurements={}
    for label,mask in strata.items():
        t=normalized_target(mask)
        dm=measurement(evalD,t);mm=measurement(evalM,t)
        info={'data':statistics(evalD,t),'MC':statistics(evalM,t)}
        summary[label]=info
        if dm is None or mm is None:continue
        mainmeasurements[label]=(dm,mm)
        boot=[]
        if label in ['all','p100_250','p250_1000']:
            for b in range(cfg['bootstrap_replicates']):
                bd=np.bincount(rng.integers(0,3,3),minlength=3)
                bm=np.r_[np.bincount(rng.integers(0,3,3),minlength=3),np.bincount(rng.integers(0,3,3),minlength=3)]
                d=measurement(evalD,t,bd);m=measurement(evalM,t,bm)
                if d is not None and m is not None:boot.append([d[k]-m[k] for k in metric_interval_keys])
            ci=np.quantile(boot,[.025,.975],axis=0) if boot else None
            info['valid_bootstrap_replicates']=len(boot)
        else:ci=None
        for k in dm:
            j=metric_interval_keys.index(k) if k in metric_interval_keys else None
            delta=None if dm[k] is None or mm[k] is None else dm[k]-mm[k]
            mainrows.append(dict(stratum=label,metric=k,data=dm[k],MC=mm[k],data_minus_MC=delta,
                                 delta_lo=None if ci is None or j is None else float(ci[0,j]),
                                 delta_hi=None if ci is None or j is None else float(ci[1,j]),
                                 ratio=None if dm[k] is None or mm[k] in [0,None] else dm[k]/mm[k]))
    for rr in mainrows:
        bound=1.0 if rr['metric'].endswith(('_median_pC','_R68_pC')) else 0.0
        rr['delta_bin_resolution_bound']=bound
        rr['delta_lo_including_bin_resolution']=None if rr['delta_lo'] is None else rr['delta_lo']-bound
        rr['delta_hi_including_bin_resolution']=None if rr['delta_hi'] is None else rr['delta_hi']+bound
    write_tsv(OUT/'response_comparison.tsv',mainrows)
    # Two available files/run give only a coarse within-run source interval.
    # These auxiliaries reuse reference files; the main comparison remains isolated.
    contrastrows=[]
    groups=[(f'data_run_{run}',ids,evalM,np.ones(40,bool)) for run,ids in
            [(15838,[12,13]),(16000,[14,15]),(16923,[16,17])]]
    groups += [('MC_minus',evalD,[1,3,5],np.arange(40)%2==0),
               ('MC_plus',evalD,[7,9,11],np.arange(40)%2==1)]
    for label,di,mi,mask in groups:
        t=normalized_target(mask);dm=measurement(di,t);mm=measurement(mi,t);boot=[]
        for b in range(cfg['bootstrap_replicates']):
            bd=np.bincount(rng.integers(0,len(di),len(di)),minlength=len(di))
            if len(mi)==6:
                bm=np.r_[np.bincount(rng.integers(0,3,3),minlength=3),np.bincount(rng.integers(0,3,3),minlength=3)]
            else:bm=np.bincount(rng.integers(0,len(mi),len(mi)),minlength=len(mi))
            d=measurement(di,t,bd);m=measurement(mi,t,bm)
            if d is not None and m is not None:boot.append([d[k]-m[k] for k in metric_interval_keys])
        ci=np.quantile(boot,[.025,.975],axis=0)
        for j,k in enumerate(metric_interval_keys):
            bound=1.0 if k.endswith(('_median_pC','_R68_pC')) else 0.0
            contrastrows.append(dict(group=label,metric=k,data=dm[k],MC=mm[k],data_minus_MC=dm[k]-mm[k],
                                     delta_lo=float(ci[0,j]),delta_hi=float(ci[1,j]),
                                     delta_lo_including_bin_resolution=float(ci[0,j])-bound,
                                     delta_hi_including_bin_resolution=float(ci[1,j])+bound,
                                     data_N=statistics(di,t)['events_common'],MC_N=statistics(mi,t)['events_common'],
                                     data_sources=len(di),MC_sources=len(mi),valid_replicates=len(boot),
                                     limitation=('run auxiliary reuses reference file; two files/run; reference weights fixed' if label.startswith('data_run') else 'charge-selected eval data vs corresponding PG production sign; three sources/side; reference fixed')))
    write_tsv(OUT/'run_sign_comparison.tsv',contrastrows)
    # Source/run controls: common calibration support, no tuning to response.
    detail=[]
    for label,ids in [(f'source_{i}',[i]) for i in range(18)]+[(f'data_run_{run}',ids) for run,ids in [(15838,[12,13]),(16000,[14,15]),(16923,[16,17])]]+[
        ('MC_minus',[0,1,2,3,4,5]),('MC_plus',[6,7,8,9,10,11]),('all_data',[12,13,14,15,16,17]),('all_MC',list(range(12)))]:
        signmask=np.ones(40,bool)
        if label.startswith('MC_minus') or (label.startswith('source_') and ids[0]<6):signmask=np.arange(40)%2==0
        if label.startswith('MC_plus') or (label.startswith('source_') and 6<=ids[0]<12):signmask=np.arange(40)%2==1
        for s in ['all','p100_250','p250_1000','xy_0_0','xy_0_1','xy_1_0','xy_1_1']:
            t=normalized_target(strata[s]&signmask);v=measurement(ids,t)
            st=statistics(ids,t)
            if v is None:
                detail.append(dict(group=label,stratum=s,metric='unsupported',value=None,N=st['events'],Neff=None))
                continue
            for k,val in v.items():detail.append(dict(group=label,stratum=s,metric=k,value=val,N=st['events_common'],Neff=st['Neff']))
    write_tsv(OUT/'source_response.tsv',detail)
    # Before weighting: full selected distributions and source composition.
    unweighted=[]
    for label,ids in [('eval_data',evalD),('eval_MC',evalM),('ref_data',refD),('ref_MC',refM),('all_data',list(range(12,18))),('all_MC',list(range(12)))]:
        mass=n[ids].sum(axis=0).astype(float);mass/=mass.sum()
        for k,val in measurement(ids,mass).items():unweighted.append(dict(sample=label,metric=k,value=val))
    write_tsv(OUT/'unweighted_response.tsv',unweighted)
    resources=dict(files=18,input_events=sum(m['read_entries'] for m in records),selected_MC=int(n[:12].sum()),selected_data=int(n[12:].sum()),
                   full_range_all_sources=True,extraction_wall_s=sum(m['wall_s'] for m in records),extraction_cpu_s=sum(m['cpu_s'] for m in records),
                   requested_bytes=sum(m['requested_bytes'] for m in records),peak_rss_MiB=max(m['peak_rss_MiB'] for m in records),
                   throughput_events_per_extraction_wall_s=sum(m['read_entries'] for m in records)/sum(m['wall_s'] for m in records),
                   shards_bytes=sum((cache/f'{i}.npz').stat().st_size for i in range(18)) if cache.is_dir() else (cache.parent/'source_histograms.tar.gz').stat().st_size,probe_histogram_denominators_exact=True,
                   charge_nonfinite_events=a['charge_nonfinite'].sum(axis=(0,1)).tolist(),count_hist_overflow_events=a['count_hist'][:,:,:,-1].sum(axis=(0,1)).tolist())
    # One comparison plot summarizes primary effect sizes with source intervals.
    fig,axs=plt.subplots(1,2,figsize=(10,4),layout='constrained')
    r=[r for r in mainrows if r['stratum']=='all' and r['metric'].endswith('_extra_pct')]
    for j,rr in enumerate(r):
        axs[0].errorbar(rr['data_minus_MC'],j,xerr=[[rr['data_minus_MC']-rr['delta_lo']],[rr['delta_hi']-rr['data_minus_MC']]],fmt='o',color='C0')
    axs[0].set_yticks(range(6),COUNTS);axs[0].axvline(0,color='grey',lw=.8);axs[0].set_xlabel('Extra activity: data - MC [percentage points]')
    for j,label in enumerate(['all','p100_250','p250_1000']):
        rr=next(r for r in mainrows if r['stratum']==label and r['metric']=='Timing_charge_median_pC')
        axs[1].errorbar(rr['data_minus_MC'],j,xerr=[[rr['data_minus_MC']-rr['delta_lo_including_bin_resolution']],[rr['delta_hi_including_bin_resolution']-rr['data_minus_MC']]],fmt='o',color='C1')
    axs[1].set_yticks(range(3),['100-1000 GeV','100-250 GeV','250-1000 GeV']);axs[1].axvline(0,color='grey',lw=.8);axs[1].set_xlabel('Timing median: data - MC [pC] (incl. bin resolution)')
    fig.suptitle('Acquired muons; fixed p/x/y/charge; source 95% intervals (Timing includes bin resolution)',fontsize=10)
    fig.savefig(OUT/'response_differences.png',dpi=150);plt.close(fig)
    resources.update(analysis_wall_s=time.perf_counter()-tick,analysis_cpu_s=time.process_time()-cpu,
                     analysis_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    write_json(OUT/'summary.json',dict(frozen_utc=cfg['frozen_utc'],support_cells=int(support.sum()),overlap_mass=float(overlap),resources=resources,strata=summary))
    print(json.dumps(dict(support_cells=int(support.sum()),resources=resources)),flush=True)


if __name__=='__main__':main()
