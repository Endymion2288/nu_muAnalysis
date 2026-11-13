#!/usr/bin/env python3
"""Spatial, truth and candidate-order checks for the complete new backward-only sample."""
import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import resource
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import binomtest

from compare_tracking import MODES, selection
from report_tracking_comparison import save_table, figure_save
from report_tracking_loss_details import summarize, measurement_index, make_viewer, draw_event
from report_tracking_truth import primary, point_at


def truth_row(event, mechanism):
    raw=event['modes']['backward']['raw']
    row=dict(run=event['run'],event=event['event'],first_failed_cut=mechanism['first_failed_cut'],
             mechanism=mechanism['mechanism'],merge_long=mechanism['merge_leader_long'])
    try:
        i,barcode,pdg=primary(raw)
    except ValueError:
        row['primary_reference_unique']=False
        return row
    row['primary_reference_unique']=True
    reference=np.array([raw['truth_'+a][i] for a in ('px','py','pz')])
    indices={}
    for mode in ('backward','merge'):
        part=event['modes'][mode]
        index=int(part['scalars']['LeadTrack_Idx'])
        j=(measurement_index(event,mode,index) if index>=0 else mechanism['blocking_merge_raw_index'])
        assert j>=0
        indices[mode]=j
        track=event['raw_truth'][mode][j];match=track['truth']
        p=np.array(track['first'][3:]);pt=np.linalg.norm(p);truth_p=np.linalg.norm(reference)
        matched=bool(match and match['barcode']==barcode and match['pdg']==pdg)
        parent=bool(matched and any(t['barcode']==raw['truth_barcode'][0] and t['pdg']==raw['truth_pdg'][0]
                                   for t in match['parents']))
        if matched:assert np.allclose(match['p_mev'],reference,rtol=2e-7,atol=1e-5)
        row.update({mode+'_matched_primary':matched,mode+'_neutrino_parent':parent,
                    mode+'_purity':match['hit_count']/track['measurements'] if match else np.nan,
                    mode+'_matched_pdg':match['pdg'] if match else 0,
                    mode+'_matched_barcode':match['barcode'] if match else 0,
                    mode+'_truth_pz_gev':reference[2]/1000,mode+'_pz_gev':p[2]/1000,
                    mode+'_abs_pz_relative':abs(p[2]/reference[2]-1),
                    mode+'_abs_p_relative':abs(pt/truth_p-1),
                    mode+'_abs_qop_error':abs(track['charge']*truth_p/pt+np.sign(pdg)),
                    mode+'_charge_flip':int(track['charge']!=-np.sign(pdg))})
        for station in (1,2,3):
            pos=np.array([raw[f'truth_st{station}_'+a][i] for a in ('x','y','z')])
            direction=np.array([raw[f'truth_st{station}_'+a][i] for a in ('px','py','pz')])
            predicted=point_at(track['states'],pos[2]) if np.all(np.isfinite(pos)) else None
            xy=radius=slope=np.nan
            if predicted is not None:
                xy=np.linalg.norm(predicted[:2]-pos[:2])
                radius=abs(np.linalg.norm(predicted[:2])-np.linalg.norm(pos[:2]))
                if np.all(np.isfinite(direction)) and direction[2]!=0 and predicted[5]!=0:
                    slope=1000*np.linalg.norm(predicted[3:5]/predicted[5]-direction[:2]/direction[2])
            row[mode+f'_st{station}_xy_mm']=xy
            row[mode+f'_st{station}_radius_mm']=radius
            row[mode+f'_st{station}_slope_mrad']=slope
    # Verify whether the actual merge candidate came from forward or backward.
    chosen=event['measurements']['merge'][indices['merge']]
    origins=[]
    for mode in ('forward','backward'):
        for j,t in enumerate(event['measurements'][mode]):
            if (np.array_equal(t['states'],chosen['states'],equal_nan=True) and
                    np.array_equal([t['chi2'],t['ndof']],[chosen['chi2'],chosen['ndof']],equal_nan=True)):
                origins.append((mode,j))
    assert origins
    row['merge_source_mode']=origins[0][0]
    row['both_primary']=row['backward_matched_primary'] and row['merge_matched_primary']
    row['both_primary_purity08']=row['both_primary'] and min(row['backward_purity'],row['merge_purity'])>=.8
    return row


def statistics(rows,scope,metric):
    b=np.array([r['backward_'+metric] for r in rows]);m=np.array([r['merge_'+metric] for r in rows])
    valid=np.isfinite(b)&np.isfinite(m);b,m=b[valid],m[valid]
    if not len(b):return None
    bw=int((b<m-1e-10).sum());mw=int((m<b-1e-10).sum())
    rng=np.random.default_rng(20261113)
    indices=rng.integers(len(b),size=(10000,len(b)))
    delta=np.median(b[indices],axis=1)-np.median(m[indices],axis=1)
    return dict(scope=scope,metric=metric,events=len(b),backward_closer=bw,merge_closer=mw,
        ties=len(b)-bw-mw,backward_median=float(np.median(b)),merge_median=float(np.median(m)),
        backward_p90=float(np.quantile(b,.9)),merge_p90=float(np.quantile(m,.9)),
        median_difference=float(np.median(b)-np.median(m)),
        median_difference_ci95_low=float(np.quantile(delta,.025)),
        median_difference_ci95_high=float(np.quantile(delta,.975)),
        sign_test_p=float(binomtest(bw,bw+mw).pvalue) if bw+mw else np.nan)


def main():
    start=time.monotonic()
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--combined',type=Path)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    manifest=[line.split('\t') for line in args.manifest.read_text().splitlines()]
    if args.combined:
        with gzip.open(args.combined,'rt') as f:events=json.load(f)
    else:events=[json.loads(Path(r[-1]).read_text()) for r in manifest]
    assert [(e['run'],e['event']) for e in events]==[(int(r[1]),int(r[2])) for r in manifest]
    cuts,_=selection(args.repo);names=[name for name,_ in cuts][6:]
    mechanisms=[];loss_events=[];truth=[];checked=0
    historical=[];performance=[]
    for e,r in zip(events,manifest):
        assert e['production_verified']
        if 'effective_reco' in e:
            assert all(s['IsolateCandidateSmoothing'] and s['MaterialEnergyLoss'] and s['MaterialScattering']
                       for s in e['effective_reco'].values())
        # Official long-track truth and normalized first states are independent
        # checks of detail-to-ntuple indexing and momentum conventions.
        for mode in MODES:
            raw=e['modes'][mode]['raw']
            for i in range(len(raw['Track_pz0'])):
                j=measurement_index(e,mode,i);t=e['raw_truth'][mode][j];match=t['truth']
                if match:
                    assert raw['t_barcode'][i]==match['barcode'] and raw['t_pdg'][i]==match['pdg']
                    assert np.allclose([raw['t_'+a][i] for a in ('px','py','pz')],match['p_mev'],rtol=2e-7,atol=1e-5)
                    assert np.isclose(raw['t_truthHitRatio'][i],match['hit_count']/(t['ndof']+5),rtol=2e-7)
                else:assert raw['t_pdg'][i]==0
                checked+=1
        if 'old89' in r[-2] or 'old_nan' in r[-2]:
            historical.append(dict(run=e['run'],event=e['event'],reason=r[-2],truth_fiducial=e.get('reference_truth_fiducial',True),
                forward_bits=e['expected_bits'][0],backward_bits=e['expected_bits'][1],merge_bits=e['expected_bits'][2],
                **{mode+'_'+key:e['modes'][mode]['scalars'][key] for mode in MODES
                   for key in ('LeadTrack_pz0','LeadTrack_Chi2_NDF','LeadTrack_r_atMaxRadius','LeadTrack_rIFT')}))
        if 'performance' in e:
            performance.append(dict(run=e['run'],event=e['event'],host=e['host'],entry=e['entry'],**e['performance']))
        if e['expected_bits'][1]==16383 and e['expected_bits'][2]!=16383:
            row=summarize(e)
            row['first_failed_cut']=next(name for j,name in enumerate(names) if not (e['expected_bits'][2]>>j)&1)
            mechanisms.append(row);loss_events.append(e);truth.append(truth_row(e,row))
    save_table(args.output/'event_mechanisms.tsv',list(mechanisms[0]),mechanisms)
    if historical:save_table(args.output/'historical_events.tsv',list(historical[0]),historical)
    if performance:save_table(args.output/'resources_by_event.tsv',list(performance[0]),performance)
    fields=list(dict.fromkeys(k for r in truth for k in r))
    save_table(args.output/'truth_by_event.tsv',fields,[{k:r.get(k,np.nan) for k in fields} for r in truth])
    scopes={'same_primary_long':[r for r in truth if r.get('both_primary') and r['merge_long']],
            'same_primary_purity08_long':[r for r in truth if r.get('both_primary_purity08') and r['merge_long']],
            'same_primary_nominal_long':[r for r in truth if r.get('both_primary') and r['merge_long'] and r['run']!=200080],
            'same_primary_nonlong':[r for r in truth if r.get('both_primary') and not r['merge_long']]}
    scopes.update({'cut_'+cut:[r for r in scopes['same_primary_long'] if r['first_failed_cut']==cut]
                   for cut in sorted({r['first_failed_cut'] for r in mechanisms})})
    metrics=['abs_pz_relative','abs_p_relative','abs_qop_error']+[f'st{s}_{a}' for s in (1,2,3) for a in ('xy_mm','radius_mm','slope_mrad')]
    stats=[v for name,rs in scopes.items() for metric in metrics if rs and (v:=statistics(rs,name,metric))]
    if stats:save_table(args.output/'accuracy_summary.tsv',list(stats[0]),stats)
    bycut=[]
    for cut in sorted({r['first_failed_cut'] for r in mechanisms}):
        rs=[r for r in mechanisms if r['first_failed_cut']==cut]
        bycut.append(dict(first_failed_cut=cut,events=len(rs),removed=sum(not r['backward_leader_retained'] for r in rs),
                          retained=sum(r['backward_leader_retained'] for r in rs)))
    save_table(args.output/'mechanism_by_cut.tsv',list(bycut[0]),bycut)
    nonlong=[r for r in mechanisms if r['blocking_has_all_stations'] is False]
    if nonlong:save_table(args.output/'nonlong_blockers.tsv',list(nonlong[0]),nonlong)
    chosen=[]
    for key in sorted({(r['first_failed_cut'],r['mechanism']) for r in mechanisms}):
        indices=[i for i,r in enumerate(mechanisms) if (r['first_failed_cut'],r['mechanism'])==key]
        chosen.append(indices[len(indices)//2])
    for i in chosen:draw_event(loss_events[i],mechanisms[i],args.output,ift_z=-1609.65)
    make_viewer(loss_events,mechanisms,Path(__file__).with_name('tracking_loss_viewer.html'),args.output/'event_viewer.html')
    viewer=args.output/'event_viewer.html'
    viewer.write_text(viewer.read_text().replace('-1590','-1609.65').replace('相同 RDO、官方 master d32b0ff3、原有分析 cuts。展示全部 89 个最终 backward-only 事件。',
        f'相同 RDO、geoRotation Calypso 88c457c1 加本地旋转及隔离 smoothing 修复、原有分析 cuts。展示全部 {len(mechanisms)} 个新版最终 backward-only 事件；坐标已恢复原约定。'))
    fig,axes=plt.subplots(1,3,figsize=(14,4.5))
    for ax,metric,label in zip(axes,('abs_pz_relative','st1_xy_mm','st1_slope_mrad'),
                               ('Absolute relative production pz error','Station 1 xy residual (mm)','Station 1 slope residual (mrad)')):
        rs=scopes['same_primary_long'];b=np.array([r['backward_'+metric] for r in rs]);m=np.array([r['merge_'+metric] for r in rs])
        ok=np.isfinite(b)&np.isfinite(m);b,m=b[ok],m[ok]
        ax.scatter(b,m,s=12,alpha=.6)
        if len(b):
            limit=max(np.quantile(b,.95),np.quantile(m,.95))*1.1
            ax.plot([0,limit],[0,limit],color='grey');ax.set_xlim(0,limit);ax.set_ylim(0,limit)
        ax.set_xlabel('Backward: '+label);ax.set_ylabel('Merge: '+label);ax.grid(alpha=.2)
    fig.suptitle('New backward-only events; both candidates matched to the primary muon; tails retained in tables')
    fig.tight_layout();figure_save(fig,args.output,'spatial_truth_comparison')
    if not args.combined:
        packed=json.dumps(events,allow_nan=True,separators=(',',':'))
        with gzip.open(args.output/'diagnostics.json.gz','wt') as f:f.write(packed)
        with gzip.open(args.output/'diagnostics.json.gz','rt') as f:assert f.read()==packed
    summary=dict(targets=len(events),backward_only=len(mechanisms),official_long_tracks_checked=checked,
        historical89=sum('old89' in r[-2] for r in manifest),old_nan=sum('old_nan' in r[-2] for r in manifest),
        mechanisms=dict(Counter(r['mechanism'] for r in mechanisms)),
        blocking_priority=dict(Counter(r['blocking_priority'] for r in mechanisms)),
        nonlong_blockers=len(nonlong),primary_reference_nonunique=sum(not r['primary_reference_unique'] for r in truth),
        same_primary_long=len(scopes['same_primary_long']),same_primary_nonlong=len(scopes['same_primary_nonlong']),
        wall_seconds=time.monotonic()-start,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    main()
