#!/usr/bin/env python3
"""Paired old/new MC reconstruction, station-reference response, purity and selection losses."""
import argparse
import csv
import json
from pathlib import Path
import time
import resource
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import binomtest
from compare_tracking import MODES, selection
from extract_tracking_station import TRACK_FIELDS, SCALARS
from report_tracking_comparison import save_table, figure_save, wilson

EDGES=np.array([0,50,100,150,200,300,500,750,1000,1500,2000,3000,5000,10000,np.inf])
EVENT_KEYS=['run','eventID','truth_pz_nu','truth_dec_x_nu','truth_dec_y_nu','truth_dec_z_nu',
            'event_cut_bits','event_individual_bits','event_scalars','primary',
            'primary_production_momentum_mev','primary_station','primary_layer_hits','scintillator','raw_primary_counts']
TRACK_KEYS=['tracks','reco_station','reco_at_primary_station','matched_truth_station','nearest_state_dz_mm','station_method']


def table(path,rows):
    if rows:save_table(path,list(rows[0]),rows)


def combine(records,version,output):
    all_ids=[];events={k:[] for k in EVENT_KEYS};tracks={k:[] for k in TRACK_KEYS};rows=[];offset=0
    for r in records:
        if r[1]!=version:continue
        with np.load(r[5]) as f:
            assert str(f['version'])==version and int(f['manifest_index'])==int(r[0])
            if 'all_run' in f:all_ids.append(np.column_stack([f['all_run'],f['all_eventID']]))
            for k in EVENT_KEYS:events[k].append(f[k])
            for k in TRACK_KEYS:
                a=f[k].copy()
                if k=='tracks':a[:,0]+=offset
                tracks[k].append(a)
            offset+=len(f['run'])
            rows.append(dict(index=int(r[0]),version=version,skip=int(r[4]),source_path=r[5],rdo=r[2],events=int(f['counts'][0,0]),
                truth=len(f['run']),final_FBM=f['counts'][:,-1].tolist(),long_tracks=len(f['tracks']),
                summary_bytes=Path(r[5]).stat().st_size,host=str(f['host']),
                performance=json.loads(str(f['performance_json'])),root_bytes=json.loads(str(f['root_bytes_json'])),
                official_long_matches_checked=int(f['official_long_matches_checked']),
                prior_cut_bits_verified=bool(f['prior_cut_bits_verified']),
                effective_reco=str(f['effective_reco_json'])))
    data={k:np.concatenate(v) for k,v in events.items()};data.update({k:np.concatenate(v) for k,v in tracks.items()})
    keys=data['run'].astype(np.int64)*1000000000+data['eventID'].astype(np.int64)
    assert len(np.unique(keys))==len(keys)
    order=np.argsort(keys);inverse=np.empty(len(keys),int);inverse[order]=np.arange(len(keys))
    for k in EVENT_KEYS:data[k]=data[k][order]
    data['tracks'][:,0]=inverse[data['tracks'][:,0].astype(int)]
    track_order=np.lexsort((data['tracks'][:,2],data['tracks'][:,1],data['tracks'][:,0]))
    for k in TRACK_KEYS:data[k]=data[k][track_order]
    if all_ids:
        ids=np.concatenate(all_ids);order=np.lexsort((ids[:,1],ids[:,0]));ids=ids[order]
        assert len(np.unique(ids,axis=0))==len(ids)
        data['all_run']=ids[:,0];data['all_eventID']=ids[:,1]
    np.savez_compressed(output/(version+'.npz'),**data)
    # Read back every column before source shards may be removed.
    with np.load(output/(version+'.npz')) as f:
        for k,v in data.items():assert np.array_equal(f[k],v,equal_nan=v.dtype.kind in 'fc'),k
    return data,rows


def derived(a):
    t=a['tracks'];col={k:t[:,i] for i,k in enumerate(TRACK_FIELDS)};idx=col['event_index'].astype(int)
    primary=(a['primary'][idx,2]==1)&(col['barcode']==a['primary'][idx,0])&(col['pdg']==a['primary'][idx,1])
    purity=np.divide(col['truth_hits'],col['measurements'],out=np.zeros(len(t)),where=col['measurements']>0)
    quality=(col['layers']>=7)&(col['ndof']>=9)&np.isfinite(col['chi2'])&(col['chi2']<15*col['ndof'])
    leaders=np.full((len(a['run']),3),-1,int)
    for m in range(3):
        s=(col['mode']==m)&(col['leader']==1);leaders[idx[s],m]=np.flatnonzero(s)
    final=a['event_cut_bits']==16383
    raw=((a['event_individual_bits'][:,:,None]>>np.arange(14))&1).astype(bool)
    track_cuts=[0,4,5,6,7,8,9,10,11]
    track_pass=raw[:,:,track_cuts].all(axis=2)
    return dict(col=col,idx=idx,primary=primary,purity=purity,quality=quality,leaders=leaders,final=final,
                raw=raw,track_pass=track_pass)


def controlled(new,old):
    raw=((new['event_individual_bits'][:,:,None]>>np.arange(14))&1).astype(bool)
    # Original ROOT charge branches are float; preserve addition precision at thresholds.
    c=old['scintillator'].astype(np.float32);bottom=c[:,6]+c[:,7];top=c[:,8]+c[:,9]
    for m in range(3):
        y=new['event_scalars'][:,m,SCALARS.index('Lead_Track_Y_atTrig')]
        raw[:,m,1]=(c[:,0]>40)&(c[:,1]>40)
        raw[:,m,2]=((y>20)&(top>20))|((y< -20)&(bottom>20))|((abs(y)<20)&(top+bottom>20))
        raw[:,m,3]=(c[:,2]>2.5)&(c[:,3]>2.5);raw[:,m,12]=c[:,4]<30;raw[:,m,13]=c[:,5]<30
    return np.logical_and.accumulate(raw,axis=2)


def rate_row(version,group,denom_name,mode,name,denom,mask):
    n=int(denom.sum());k=int((denom&mask).sum());lo,hi=wilson(k,n)
    return dict(version=version,group=group,denominator_name=denom_name,mode=mode,stage=name,
                denominator=n,passed=k,failed=n-k,efficiency_percent=100*k/n if n else np.nan,
                wilson68_low_percent=100*lo,wilson68_high_percent=100*hi)


def basic_metrics(data,der,output,groups,truth_masks,cuts):
    efficiencies=[];losses=[];purities=[];cutloss=[];truthsteps=[]
    for group,gmask in groups.items():
        for name,mask in truth_masks.items():
            truthsteps.append(dict(group=group,truth_stage=name,passed=int((gmask&mask).sum()),
                                   fiducial_events=int(gmask.sum())))
    for version,a in data.items():
        d=der[version];col=d['col'];idx=d['idx'];n=len(a['run'])
        for m,mode in enumerate(MODES):
            l=d['leaders'][:,m];has=l>=0;li=np.maximum(l,0)
            correct=has&d['primary'][li]&(d['purity'][li]>=.7)
            pz=a['event_scalars'][:,m,SCALARS.index('LeadTrack_pz0')]
            counts=a['raw_primary_counts'][:,m]
            stages=dict(any_primary_raw=counts[:,0]>0,any_primary_long=counts[:,1]>0,
                any_primary_quality=counts[:,2]>0,has_long=has,correct_leader=correct,
                track_cuts=d['track_pass'][:,m],track_cuts_correct=d['track_pass'][:,m]&correct,
                final=d['final'][:,m],final_correct=d['final'][:,m]&correct)
            if version=='new':stages['final_fixed_old_scintillator']=d['control'][:,:,-1][:,m]
            for group,gmask in groups.items():
                for denom_name,den in [('fiducial',truth_masks['fiducial']),('truth_station_acceptance',truth_masks['truth_station_acceptance'])]:
                    denominator=gmask&den
                    for name,mask in stages.items():efficiencies.append(rate_row(version,group,denom_name,mode,name,denominator,mask))
                for scope,selected in [('all_leaders',has),('track_cuts',d['track_pass'][:,m]),('final',d['final'][:,m])]:
                    selected=selected&gmask
                    for threshold in [.5,.7,.9]:
                        matched=has&d['primary'][li]&(d['purity'][li]>=threshold)
                        purities.append(rate_row(version,group,scope,mode,'correct_primary_purity'+str(threshold),selected,matched))
                den=gmask&truth_masks['truth_station_acceptance']
                final=d['final'][:,m]
                # Exhaustive, mutually exclusive losses among truth-accepted events.
                category=np.full(n,'selected_correct',dtype=object)
                category[final&~correct]='selected_wrong_or_low_purity'
                category[~final]='other_cut_failure'
                category[~final&d['track_pass'][:,m]]='scintillator_failure_after_track_cuts'
                category[~final&~d['track_pass'][:,m]&correct]='correct_leader_track_cut_failure'
                category[~final&~correct&(counts[:,1]>0)]='primary_long_exists_wrong_leader'
                category[~final&(counts[:,1]==0)&(counts[:,0]>0)]='primary_raw_only'
                category[~final&(counts[:,0]==0)]='no_high_purity_primary_raw'
                assert np.array_equal(category=='selected_correct',final&correct)
                labels=sorted(set(category[den]))
                assert sum(int((den&(category==label)).sum()) for label in labels)==int(den.sum())
                for label in labels:
                    losses.append(dict(version=version,group=group,mode=mode,category=label,
                        events=int((den&(category==label)).sum()),denominator=int(den.sum())))
                # First failing cut in the actual cumulative analysis, with no loss dropped.
                failed_total=0
                for j,name in enumerate(cuts):
                    before=np.ones(n,bool) if j==0 else (a['event_cut_bits'][:,m]&(1<<(j-1)))!=0
                    fail=den&before&((a['event_cut_bits'][:,m]&(1<<j))==0)
                    failed_total+=int(fail.sum())
                    cutloss.append(dict(version=version,group=group,mode=mode,first_failed_cut=name,events=int(fail.sum()),denominator=int(den.sum())))
                assert failed_total==int((den&~final).sum())
            # Every per-event loss remains reconstructible from the combined caches.
    for name,rows in [('efficiency',efficiencies),('truth_acceptance',truthsteps),('selection_purity',purities),
                      ('truth_accepted_losses',losses),('first_failed_cut',cutloss)]:table(output/(name+'.tsv'),rows)
    binned=[]
    variables={'primary_station1_pz_gev':(data['old']['primary_station'][:,0,5]/1000,EDGES),
        'nu_pz_gev':(data['old']['truth_pz_nu'],np.array([100,200,300,500,1000,2000,5000,10000,np.inf])),
        'vertex_radius_mm':(np.hypot(data['old']['truth_dec_x_nu'],data['old']['truth_dec_y_nu']),np.arange(0,101,20)),
        'vertex_z_mm':(data['old']['truth_dec_z_nu'],np.r_[np.arange(-3000,-1999,100),-1950,-1769.65,-1719.65,-1669.65,-1619.65])}
    for version,a in data.items():
        d=der[version]
        for m,mode in enumerate(MODES):
            leader=d['leaders'][:,m];li=np.maximum(leader,0)
            correct=(leader>=0)&d['primary'][li]&(d['purity'][li]>=.7)
            stages={'primary_raw':a['raw_primary_counts'][:,m,0]>0,'primary_long':a['raw_primary_counts'][:,m,1]>0,
                'primary_quality':a['raw_primary_counts'][:,m,2]>0,'correct_leader':correct,
                'final':d['final'][:,m],'final_correct':d['final'][:,m]&correct}
            for variable,(value,edges) in variables.items():
                for lo,hi in zip(edges[:-1],edges[1:]):
                    den=truth_masks['truth_station_acceptance']&(value>=lo)&(value<hi)
                    for stage,mask in stages.items():
                        r=rate_row(version,'all','truth_station_acceptance',mode,stage,den,mask)
                        r.update(variable=variable,low=lo,high=hi);binned.append(r)
    table(output/'binned_efficiency.tsv',binned)
    return efficiencies,purities


def particle_content(data,der,groups,output):
    rows=[];numerical=[]
    for version,a in data.items():
        d=der[version];c=d['col']
        for m,mode in enumerate(MODES):
            lead=d['leaders'][:,m];has=lead>=0;li=np.maximum(lead,0)
            pdg=c['pdg'][li];purity=d['purity'][li];primary=d['primary'][li]
            labels=np.full(len(has),'other_particle',dtype=object)
            labels[abs(pdg)>100]='hadron';labels[abs(pdg)==11]='electron';labels[abs(pdg)==13]='other_muon'
            labels[purity<.7]='low_purity_match';labels[primary]='primary_muon_low_purity';labels[primary&(purity>=.7)]='primary_muon_high_purity'
            labels[c['barcode'][li]==0]='unmatched';labels[~has]='no_long'
            for group,g in groups.items():
                for scope,selected in [('leaders',has),('track_cuts',d['track_pass'][:,m]),('final',d['final'][:,m])]:
                    select=g&selected
                    for label in sorted(set(labels[select])):
                        rows.append(dict(version=version,group=group,mode=mode,scope=scope,particle_class=label,
                            events=int((select&(labels==label)).sum()),denominator=int(select.sum())))
                    sel=select&has;index=li[sel]
                    matched=sel&primary&(purity>=.7);j=li[matched]
                    numerical.append(dict(version=version,group=group,mode=mode,scope=scope,events=int(sel.sum()),
                        nonfinite_chi2=int((~np.isfinite(c['chi2'][index])).sum()),
                        nonpositive_ndof=int((c['ndof'][index]<=0).sum()),nonfinite_pz=int((~np.isfinite(c['pz_mev'][index])).sum()),
                        primary_pairs=int(matched.sum()),primary_charge_flips=int((c['charge'][j]!=-np.sign(c['pdg'][j])).sum())))
    table(output/'particle_content.tsv',rows);table(output/'numerical_and_charge.tsv',numerical)


def local_cut_migrations(data,der,groups,output):
    rows=[]
    for version,a in data.items():
        d=der[version]
        for m,mode in enumerate(MODES):
            leader=d['leaders'][:,m];has=leader>=0;li=np.maximum(leader,0)
            correct=has&d['primary'][li]&(d['purity'][li]>=.7)
            for station in range(3):
                t=a['primary_station'][:,station];r=a['reco_at_primary_station'][li,station]
                with np.errstate(invalid='ignore',divide='ignore'):
                    truth_values={'pz_gt100GeV':t[:,5]>100000,'r_lt95mm':np.linalg.norm(t[:,:2],axis=1)<95,
                        'theta_lt25mrad':1000*np.arctan2(np.linalg.norm(t[:,3:5],axis=1),t[:,5])<25}
                    reco_values={'pz_gt100GeV':r[:,5]>100000,'r_lt95mm':np.linalg.norm(r[:,:2],axis=1)<95,
                        'theta_lt25mrad':1000*np.arctan2(np.linalg.norm(r[:,3:5],axis=1),r[:,5])<25}
                for group,g in groups.items():
                    valid=g&(a['primary'][:,2]==1)&np.isfinite(t).all(axis=1)&(t[:,5]>0)
                    fitted=has&np.isfinite(r).all(axis=1)
                    for cut,tp in truth_values.items():
                        rp=reco_values[cut]&fitted
                        for scope,select in [('all_primary_truth',valid),('correct_primary_leader',valid&correct)]:
                            rows.append(dict(version=version,group=group,mode=mode,station=station+1,scope=scope,cut=cut,
                                denominator=int(select.sum()),truth_pass=int((select&tp).sum()),reco_pass=int((select&rp).sum()),
                                truth_pass_reco_pass=int((select&tp&rp).sum()),truth_pass_reco_fail=int((select&tp&~rp).sum()),
                                truth_fail_reco_pass=int((select&~tp&rp).sum()),both_fail=int((select&~tp&~rp).sum()),
                                truth_pass_missing_local_fit=int((select&tp&~fitted).sum()),
                                truth_pass_wrong_or_low_purity_leader=int((select&tp&fitted&~correct).sum())))
    table(output/'local_cut_migrations.tsv',rows)


def residual_summary(x):
    x=x[np.isfinite(x)]
    if not len(x):return dict(valid=0,median=np.nan,q16=np.nan,q84=np.nan,central68_half_width=np.nan,
                             median_absolute=np.nan,q68_absolute=np.nan,tail_absolute_gt_half=0)
    q=np.quantile(x,[.16,.5,.84]);return dict(valid=len(x),median=q[1],q16=q[0],q84=q[2],central68_half_width=(q[2]-q[0])/2,
        median_absolute=float(np.median(abs(x))),q68_absolute=float(np.quantile(abs(x),.68)),tail_absolute_gt_half=int((abs(x)>.5).sum()))


def response_metrics(data,der,output,groups,truth_masks):
    residuals=[];coverage=[];paired=[];bins=[];matrices=[];flows=[];accuracy=[];binned_residuals=[]
    all_responses={}
    for version,a in data.items():
        d=der[version];c=d['col'];idx=d['idx'];good=d['primary']&(d['purity']>=.7)
        all_responses[version]={}
        for m,mode in enumerate(MODES):
            scopes=dict(matched_long=good&(c['mode']==m),matched_quality=good&d['quality']&(c['mode']==m),
                matched_leader=good&(c['mode']==m)&(c['leader']==1),
                matched_final_leader=good&(c['mode']==m)&(c['leader']==1)&d['final'][idx,m])
            for station in range(3):
                pred=a['reco_station'][:,station];truth=a['matched_truth_station'][:,station]
                rp=np.linalg.norm(pred[:,3:],axis=1);tp=np.linalg.norm(truth[:,3:],axis=1)
                with np.errstate(invalid='ignore',divide='ignore'):
                    responses=dict(p_relative=rp/tp-1,pz_relative=pred[:,5]/truth[:,5]-1,
                        qop_normalized=(c['charge']/rp+np.sign(c['pdg'])/tp)*tp,
                        slope_mrad=1000*np.linalg.norm(pred[:,3:5]/pred[:,5,None]-truth[:,3:5]/truth[:,5,None],axis=1),
                        xy_mm=np.linalg.norm(pred[:,:2]-truth[:,:2],axis=1))
                all_responses[version][m,station]=responses
                for group,gmask in groups.items():
                    for scope,mask in scopes.items():
                        selected=mask&gmask[idx];valid=selected&np.isfinite(responses['p_relative'])
                        coverage.append(dict(version=version,group=group,mode=mode,station=station+1,scope=scope,
                            candidates=int(selected.sum()),valid_local_pairs=int(valid.sum()),
                            missing_truth=int((selected&~np.isfinite(truth).all(axis=1)).sum()),
                            missing_fit_at_truth_z=int((selected&np.isfinite(truth).all(axis=1)&~np.isfinite(pred).all(axis=1)).sum()),
                            interpolation=int((valid&(a['station_method'][:,station]==1)).sum()),
                            nearest_within5mm=int((valid&(a['station_method'][:,station]==2)).sum()),
                            median_nearest_dz_mm=float(np.median(a['nearest_state_dz_mm'][valid,station])) if valid.any() else np.nan))
                        for metric,x in responses.items():
                            residuals.append(dict(version=version,group=group,mode=mode,station=station+1,scope=scope,metric=metric,unit=('mm' if metric=='xy_mm' else 'mrad' if metric=='slope_mrad' else 'dimensionless'),**residual_summary(x[selected])))
                            if metric not in ['p_relative','pz_relative']:continue
                            finite_metric=selected&np.isfinite(x)
                            for threshold in [.1,.2,.5]:
                                r=rate_row(version,group,scope,mode,'absolute_relative_error_lt'+str(threshold),finite_metric,abs(x)<threshold)
                                r['uncertainty_unit']='one_leader_per_event'
                                if scope not in ['matched_leader','matched_final_leader']:
                                    r['wilson68_low_percent']=np.nan;r['wilson68_high_percent']=np.nan
                                    r['uncertainty_unit']='candidate_counts_only; correlated candidates, CI not measured'
                                r.update(station=station+1,metric=metric);accuracy.append(r)
                            if group=='all' and scope in ['matched_quality','matched_leader','matched_final_leader']:
                                for lo,hi in zip(EDGES[:-1],EDGES[1:]):
                                    local=selected&(truth[:,5]>=lo*1000)&(truth[:,5]<hi*1000)
                                    binned_residuals.append(dict(version=version,mode=mode,station=station+1,scope=scope,
                                        metric=metric,truth_pz_low_gev=lo,truth_pz_high_gev=hi,**residual_summary(x[local])))
                # Momentum migrations include wrong/no match in purity denominator.
                leaders=d['leaders'][:,m];has=leaders>=0;li=np.maximum(leaders,0)
                reco=a['reco_at_primary_station'][li,station,5]/1000
                truthpz=a['primary_station'][:,station,5]/1000
                correct=has&good[li]
                finite=has&np.isfinite(reco)&np.isfinite(truthpz)&(truthpz>0)
                tb=np.searchsorted(EDGES,truthpz,side='right')-1;rb=np.searchsorted(EDGES,reco,side='right')-1
                for group,gmask in groups.items():
                    for scope,selected in [('leader',has),('track_cuts',d['track_pass'][:,m]),('final',d['final'][:,m])]:
                        source=selected&gmask
                        flows.append(dict(version=version,group=group,mode=mode,station=station+1,scope=scope,
                            selected_events=int(source.sum()),finite_positive_truth=int((source&finite).sum()),
                            missing_local_reco=int((source&~np.isfinite(reco)).sum()),
                            negative_reco_pz=int((source&np.isfinite(reco)&(reco<0)).sum()),
                            missing_positive_primary_truth=int((source&(~np.isfinite(truthpz)|(truthpz<=0))).sum())))
                        selected=source&finite
                        matched=selected&correct
                        matrix=np.histogram2d(truthpz[matched],reco[matched],bins=(EDGES,EDGES))[0].astype(int)
                        for ti,ri in zip(*np.nonzero(matrix)):
                            matrices.append(dict(version=version,group=group,mode=mode,station=station+1,scope=scope,
                                truth_bin=int(ti),reco_bin=int(ri),events=int(matrix[ti,ri])))
                        den=gmask&truth_masks['truth_station_acceptance']&np.isfinite(truthpz)
                        for b,(lo,hi) in enumerate(zip(EDGES[:-1],EDGES[1:])):
                            ntruth=int((den&(tb==b)).sum())
                            nreco=int((source&has&np.isfinite(reco)&(rb==b)).sum())
                            matchedsame=int((matched&(tb==b)&(rb==b)).sum())
                            accepted_same=int((matched&den&(tb==b)&(rb==b)).sum())
                            matchedtruth=int((matched&(tb==b)).sum());matchedreco=int((matched&(rb==b)).sum())
                            purity_low,purity_high=wilson(matchedsame,nreco)
                            stability_low,stability_high=wilson(matchedsame,matchedtruth)
                            efficiency_low,efficiency_high=wilson(accepted_same,ntruth)
                            bins.append(dict(version=version,group=group,mode=mode,station=station+1,scope=scope,
                                low_gev=lo,high_gev=hi,truth_accepted_events=ntruth,reco_bin_events=nreco,
                                correct_primary_reco_bin_events=matchedreco,matched_truth_bin_events=matchedtruth,
                                same_bin_events=matchedsame,truth_accepted_same_bin_events=accepted_same,
                                momentum_bin_purity_percent=100*matchedsame/nreco if nreco else np.nan,
                                momentum_bin_purity_wilson68_low_percent=100*purity_low,
                                momentum_bin_purity_wilson68_high_percent=100*purity_high,
                                bin_stability_percent=100*matchedsame/matchedtruth if matchedtruth else np.nan,
                                bin_stability_wilson68_low_percent=100*stability_low,
                                bin_stability_wilson68_high_percent=100*stability_high,
                                accepted_diagonal_efficiency_percent=100*accepted_same/ntruth if ntruth else np.nan,
                                accepted_diagonal_efficiency_wilson68_low_percent=100*efficiency_low,
                                accepted_diagonal_efficiency_wilson68_high_percent=100*efficiency_high))
    # Paired leaders on identical events, primary identity, and same station validity.
    for m,mode in enumerate(MODES):
        for station in range(3):
            bo=der['old']['leaders'][:,m];bn=der['new']['leaders'][:,m];has=(bo>=0)&(bn>=0)
            io=np.maximum(bo,0);inew=np.maximum(bn,0)
            matched=has&der['old']['primary'][io]&der['new']['primary'][inew]& \
                (der['old']['purity'][io]>=.7)&(der['new']['purity'][inew]>=.7)
            for group,gmask in groups.items():
                scopes=dict(common_matched_leaders=matched&gmask,
                    both_final=matched&gmask&der['old']['final'][:,m]&der['new']['final'][:,m],
                    truth_accepted_common=matched&gmask&truth_masks['truth_station_acceptance'])
                for scope,mask in scopes.items():
                    for metric in ['p_relative','pz_relative','qop_normalized','slope_mrad','xy_mm']:
                        x=all_responses['old'][m,station][metric][io];y=all_responses['new'][m,station][metric][inew]
                        select=mask&np.isfinite(x)&np.isfinite(y);x,y=abs(x[select]),abs(y[select])
                        if not len(x):continue
                        oldwin=int((x<y-1e-10).sum());newwin=int((y<x-1e-10).sum());delta=y-x
                        paired.append(dict(group=group,mode=mode,station=station+1,scope=scope,metric=metric,pairs=len(x),
                            old_closer=oldwin,new_closer=newwin,ties=len(x)-oldwin-newwin,
                            sign_p=float(binomtest(newwin,newwin+oldwin).pvalue) if newwin+oldwin else np.nan,
                            old_median_absolute=float(np.median(x)),new_median_absolute=float(np.median(y)),
                            mean_absolute_difference_new_minus_old=float(delta.mean()),
                            mean_difference_se=float(delta.std(ddof=1)/np.sqrt(len(delta))) if len(delta)>1 else np.nan))
    mode_pairs=[]
    for version,a in data.items():
        d=der[version]
        for left,right in [(0,1),(0,2),(1,2)]:
            l=d['leaders'][:,left];r=d['leaders'][:,right];il=np.maximum(l,0);ir=np.maximum(r,0)
            matched=(l>=0)&(r>=0)&d['primary'][il]&d['primary'][ir]&(d['purity'][il]>=.7)&(d['purity'][ir]>=.7)
            for group,gmask in groups.items():
                for scope,mask in [('common_matched_leaders',matched&gmask),
                    ('both_final',matched&gmask&d['final'][:,left]&d['final'][:,right])]:
                    for station in range(3):
                        for metric in ['p_relative','pz_relative','qop_normalized','slope_mrad','xy_mm']:
                            x=all_responses[version][left,station][metric][il]
                            y=all_responses[version][right,station][metric][ir]
                            valid=mask&np.isfinite(x)&np.isfinite(y);x,y=abs(x[valid]),abs(y[valid])
                            if not len(x):continue
                            lw=int((x<y-1e-10).sum());rw=int((y<x-1e-10).sum());delta=y-x
                            mode_pairs.append(dict(version=version,group=group,left=MODES[left],right=MODES[right],
                                scope=scope,station=station+1,metric=metric,pairs=len(x),left_closer=lw,right_closer=rw,
                                ties=len(x)-lw-rw,left_median_absolute=float(np.median(x)),right_median_absolute=float(np.median(y)),
                                sign_p=float(binomtest(rw,lw+rw).pvalue) if lw+rw else np.nan,
                                mean_absolute_difference_right_minus_left=float(delta.mean()),
                                mean_difference_se=float(delta.std(ddof=1)/np.sqrt(len(delta))) if len(delta)>1 else np.nan))
    for name,rows in [('station_residuals',residuals),('station_accuracy_fractions',accuracy),
                      ('station_binned_residuals',binned_residuals),('station_coverage',coverage),('paired_station_accuracy',paired),
                      ('paired_mode_station_accuracy',mode_pairs),
                      ('momentum_bin_purity',bins),('momentum_response_matrix',matrices),('momentum_response_flows',flows)]:table(output/(name+'.tsv'),rows)
    return residuals,bins


def performance_summary(audit,output):
    rows=[];summary={}
    for version in ['old','new']:
        selected=[r for r in audit if r['version']==version];steps={};root_bytes={}
        for r in selected:
            for name,value in r['performance'].items():
                measurements=dict(re.findall(r'(\w+)=(\d+(?:\.\d+)?)',value))
                wall=float(measurements['wall_seconds']);rss=int(measurements['max_rss_kib'])
                user=float(measurements['user_seconds']);system=float(measurements['system_seconds'])
                rows.append(dict(version=version,index=r['index'],skip=r['skip'],step=name,events=r['events'],
                    wall_s=wall,max_rss_kib=rss,user_s=user,system_s=system))
                steps.setdefault(name,[]).append((wall,rss,user,system))
            for name,value in r['root_bytes'].items():root_bytes[name]=root_bytes.get(name,0)+value
        events=sum(r['events'] for r in selected)
        summary[version]=dict(events=events,jobs=len(selected),summary_bytes=sum(r['summary_bytes'] for r in selected),
            transient_root_bytes=root_bytes,steps={})
        for name,values in steps.items():
            a=np.asarray(values);total=float(a[:,0].sum())
            summary[version]['steps'][name]=dict(wall_total_s=total,median_job_wall_s=float(np.median(a[:,0])),
                max_rss_kib=int(a[:,1].max()),cpu_user_total_s=float(a[:,2].sum()),cpu_system_total_s=float(a[:,3].sum()),
                events_per_summed_wall_s=events/total if total else np.nan)
    table(output/'performance.tsv',rows)
    (output/'performance_summary.json').write_text(json.dumps(summary,indent=2)+'\n')


def version_migrations(data,der,groups,truth_masks,output):
    rows=[]
    for group,g in groups.items():
        for denom,mask in [('fiducial',truth_masks['fiducial']),('truth_station_acceptance',truth_masks['truth_station_acceptance'])]:
            select=g&mask;n=int(select.sum())
            for m,mode in enumerate(MODES):
                for stage in ['track_pass','final','control_final']:
                    a=der['old']['final'][:,m] if stage=='control_final' else der['old'][stage][:,m]
                    b=der['new']['control'][:,m,-1] if stage=='control_final' else der['new'][stage][:,m]
                    lost=int((select&a&~b).sum());gain=int((select&~a&b).sum());delta=(gain-lost)/n if n else np.nan
                    rows.append(dict(group=group,denominator_name=denom,mode=mode,stage=stage,denominator=n,
                        old_pass=int((select&a).sum()),new_pass=int((select&b).sum()),old_only=lost,new_only=gain,
                        both=int((select&a&b).sum()),delta_percentage_points=100*delta,
                        paired_se_percentage_points=100*np.sqrt(max(0,(lost+gain)/n-delta**2)/n) if n else np.nan))
    table(output/'version_migrations.tsv',rows)


def plots(data,der,output,truth_masks,residuals,bins):
    fig,axes=plt.subplots(3,3,figsize=(14,11))
    for m,mode in enumerate(MODES):
        for station in range(3):
            ax=axes[station,m]
            for version,color in [('old','tab:blue'),('new','tab:orange')]:
                a=data[version];d=der[version];c=d['col'];selected=d['primary']&(d['purity']>=.7)&(c['mode']==m)&(c['leader']==1)
                p=a['reco_station'][:,station,5];t=a['matched_truth_station'][:,station,5]
                with np.errstate(invalid='ignore',divide='ignore'):x=p/t-1
                x=x[selected&np.isfinite(x)]
                ax.hist(x,bins=np.linspace(-1,1,81),weights=np.ones(len(x))/max(1,len(x)),histtype='step',color=color,label=version)
            ax.set_title(f'{mode}, Station {station+1}');ax.grid(alpha=.2)
            ax.set_xlabel('(reco pz - station reference pz) / reference pz');ax.set_ylabel('Fraction / bin');ax.legend()
    fig.suptitle('Same primary muon, purity >=0.7; station direction + HepMC momentum scale; tails retained in tables')
    fig.tight_layout();figure_save(fig,output,'station_pz_response')
    fig,axes=plt.subplots(1,3,figsize=(14,4.5))
    for m,mode in enumerate(MODES):
        for version,style in [('old','-'),('new','--')]:
            rows=[r for r in bins if r['version']==version and r['group']=='all' and r['mode']==mode and r['station']==1 and r['scope']=='final']
            centers=[np.sqrt(max(1,r['low_gev'])*r['high_gev']) for r in rows if np.isfinite(r['high_gev'])]
            axes[0].plot(centers,[r['momentum_bin_purity_percent'] for r in rows if np.isfinite(r['high_gev'])],style,label=version+' '+mode)
            axes[1].plot(centers,[r['bin_stability_percent'] for r in rows if np.isfinite(r['high_gev'])],style,label=version+' '+mode)
            axes[2].plot(centers,[r['accepted_diagonal_efficiency_percent'] for r in rows if np.isfinite(r['high_gev'])],style,label=version+' '+mode)
    for ax,label in zip(axes,['Momentum-bin purity (%)','Matched bin stability (%)','Truth-accepted diagonal efficiency (%)']):
        ax.set_xscale('log');ax.set_ylim(0,105);ax.set_xlabel('Station 1 pz bin (GeV)');ax.set_ylabel(label);ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.tight_layout();figure_save(fig,output,'momentum_bin_metrics')
    fig,axes=plt.subplots(1,3,figsize=(14,4.5))
    for m,mode in enumerate(MODES):
        ax=axes[m];t=data['old']['primary_station'][:,0,5]/1000
        edges=np.r_[EDGES[:-1],20000]
        ax.hist(t[np.isfinite(t)],bins=edges,histtype='step',label='truth primary, fiducial',color='black')
        for version in ['old','new']:
            a=data[version];d=der[version];li=np.maximum(d['leaders'][:,m],0);sel=d['final'][:,m]&(d['leaders'][:,m]>=0)
            p=a['reco_at_primary_station'][li,0,5]/1000
            ax.hist(p[sel&np.isfinite(p)],bins=edges,histtype='step',label=version+' final leader')
        ax.set_xscale('log');ax.set_yscale('log');ax.set_xlim(30,20000);ax.set_xlabel('Station 1 pz (GeV)');ax.set_ylabel('Events / bin');ax.set_title(mode);ax.legend(fontsize=8);ax.grid(alpha=.2)
    fig.suptitle('Truth and selected reconstructed spectra; unweighted counts; different selection populations')
    fig.tight_layout();figure_save(fig,output,'momentum_spectra')


def main():
    start=time.monotonic();p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--allow-partial',action='store_true')
    p.add_argument('--combined',type=Path)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    records=[r.split('\t') for r in args.manifest.read_text().splitlines()]
    data={};audit=[]
    for version in ['old','new']:
        if args.combined:
            with np.load(args.combined/(version+'.npz')) as f:data[version]={k:f[k] for k in f.files}
        else:
            data[version],rows=combine(records,version,args.output);audit+=rows
    if args.combined:
        audit=json.loads((args.combined/'source_audit.json').read_text())
        configurations=json.loads((args.combined/'effective_reco_configurations.json').read_text())
    else:
        configurations={}
        for row in audit:
            value=row.pop('effective_reco')
            matches=[key for key,existing in configurations.items() if existing==value]
            key=matches[0] if matches else row['version']+'_'+str(len(configurations))
            configurations[key]=value;row['effective_reco_key']=key
    (args.output/'effective_reco_configurations.json').write_text(json.dumps(configurations,indent=2)+'\n')
    original_manifest=args.output/'input_manifest.tsv'
    if original_manifest.exists():
        sources={(r[1],int(r[0]),int(r[4])):r[5] for r in
                 (line.split('\t') for line in original_manifest.read_text().splitlines())}
        for row in audit:row['source_path']=sources[row['version'],row['index'],row['skip']]
    old,new=data['old'],data['new']
    for k in ['run','eventID','truth_pz_nu','truth_dec_x_nu','truth_dec_y_nu','truth_dec_z_nu','primary',
              'primary_production_momentum_mev','primary_station','primary_layer_hits']:
        assert np.array_equal(old[k],new[k],equal_nan=old[k].dtype.kind in 'fc'),('old/new truth',k)
    if not args.allow_partial:
        assert np.array_equal(old['all_run'],new['all_run']) and np.array_equal(old['all_eventID'],new['all_eventID'])
        assert len(old['run'])==383670
        if audit:
            for version in ['old','new']:assert sum(r['events'] for r in audit if r['version']==version)==3374987
    table(args.output/'files.tsv',[{k:(json.dumps(v) if isinstance(v,(dict,list)) else v) for k,v in r.items()
                                  if k not in ['performance','root_bytes']} for r in audit])
    der={k:derived(v) for k,v in data.items()};der['new']['control']=controlled(new,old)
    if not args.allow_partial:
        assert der['old']['final'].sum(axis=0).tolist()==[92937,103985,104930]
        assert der['new']['final'].sum(axis=0).tolist()==[87986,99060,102760]
        assert der['new']['control'][:,:,-1].sum(axis=0).tolist()==[88961,100142,103883]
    if audit:performance_summary(audit,args.output)
    truth=old['primary_station'];unique=old['primary'][:,2]==1
    finite=unique&np.isfinite(truth).all(axis=(1,2))&(truth[:,:,5]>0).all(axis=1)
    radius=(np.linalg.norm(truth[:,:,:2],axis=2)<95).all(axis=1)
    localpz=(truth[:,:,5]>100000).all(axis=1)
    theta=(1000*np.arctan2(np.linalg.norm(truth[:,:,3:5],axis=2),truth[:,:,5])<25).all(axis=1)
    layers=(old['primary_layer_hits']>0).sum(axis=1)>=7
    masks=dict(fiducial=np.ones(len(unique),bool),unique_primary=unique,three_stations=finite,
        truth_layers_ge7=finite&layers,truth_radius_lt95=finite&layers&radius,
        truth_pz_gt100=finite&layers&radius&localpz,truth_station_acceptance=finite&layers&radius&localpz&theta)
    groups=dict(all=np.ones(len(unique),bool),nominal=old['run']!=200080)
    groups.update({str(r):old['run']==r for r in np.unique(old['run'])})
    active_cuts,skipped=selection(args.repo)
    cuts=[n for n,_ in active_cuts][6:]
    definitions=dict(active_analysis_cuts=active_cuts,skipped_analysis_cuts=skipped,
        truth_acceptance='truth-fiducial; unique primary muon; finite positive-pz reference at all 3 stations; >=7 hit layers; mean station r<95mm, reference pz>100GeV and theta<25mrad at all 3 stations',
        truth_acceptance_limit='proxy only: no truth IFT/rmax surface, fit chi2/ndof, scintillator response, or transported G4 momentum',
        primary='unique signed muon PDG inferred from incident neutrino, production xyz equal neutrino decay xyz within 1e-4 mm, searched among truth particles persisted by ntuple',
        truth_hit_purity='dominant truth barcode contributions / track measurements; default >=0.7; thresholds 0.5, 0.7, 0.9 also tabulated',
        momentum_bin_purity='correct primary AND same truth/reco pz bin / all selected leaders with finite local reco pz in that bin; missing truth/local fit is reported separately',
        matched_bin_stability='same bin / correct primary selected leaders in the truth bin',
        accepted_diagonal_efficiency='truth-accepted selected correct primary in same bin / truth-accepted events in truth bin',
        weighting='unweighted events; nominal excludes alternative generator run 200080; no systematic uncertainties')
    (args.output/'selection_definition.json').write_text(json.dumps(definitions,indent=2)+'\n')
    reference_audit=[]
    production=np.linalg.norm(old['primary_production_momentum_mev'],axis=1)
    for station in range(3):
        magnitude=np.linalg.norm(truth[:,station,3:],axis=1)
        valid=unique&np.isfinite(magnitude)&(production>0)
        ratio=magnitude[valid]/production[valid]
        reference_audit.append(dict(station=station+1,events=int(valid.sum()),
            median_station_to_production_p=float(np.median(ratio)),min_ratio=float(np.min(ratio)),max_ratio=float(np.max(ratio)),
            within_one_percent=int((abs(ratio-1)<.01).sum())))
    table(args.output/'reference_magnitude_audit.tsv',reference_audit)
    eff,pur=basic_metrics(data,der,args.output,groups,masks,cuts)
    res,bins=response_metrics(data,der,args.output,groups,masks)
    particle_content(data,der,groups,args.output)
    local_cut_migrations(data,der,groups,args.output)
    version_migrations(data,der,groups,masks,args.output);plots(data,der,args.output,masks,res,bins)
    summary=dict(common_truth_fiducial=len(unique),truth_accepted=int(masks['truth_station_acceptance'].sum()),
        prior_cut_bits_verified=all(r['prior_cut_bits_verified'] for r in audit),
        old_new_truth_exact=True,shards=len(audit),events_per_version={v:sum(r['events'] for r in audit if r['version']==v) for v in data},
        local_reference='station-averaged SiHit direction times linked HepMC momentum magnitude; NOT transported G4 momentum',
        station_matching='interpolation at truth mean z; bracketing gap <=150mm; outside-range nearest state only <=5mm',
        full_g4_local_momentum_measured=False,wall_s=time.monotonic()-start,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (args.output/'source_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
