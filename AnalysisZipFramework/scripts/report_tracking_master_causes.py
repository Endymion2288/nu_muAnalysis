#!/usr/bin/env python3
"""Classify paired old/latest losses before attributing them to better rejection."""
import argparse
import json
from pathlib import Path
import resource
import time

import numpy as np
from compare_tracking import MODES, selection
from report_tracking_ablation import load_cache
from report_tracking_material import truth_masks
from report_tracking_station import derived, table


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();start=time.monotonic();out=args.output;out.mkdir(parents=True,exist_ok=True)
    data={v:load_cache(args.repo/p) for v,p in [
        ('old','workbook/stage203_station_truth/old.npz'),
        ('latest','workbook/stage208_master_integration/full/latest.npz')]}
    a,b=data.values();assert np.array_equal(a['eventID'],b['eventID']) and np.array_equal(a['run'],b['run'])
    ds={v:derived(d) for v,d in data.items()};masks=truth_masks(a)
    cuts=[name for name,_ in selection(args.repo)[0]][6:]
    rows=[];fail=[];stages=[];events=[];accuracy=[];extreme=[]
    for m,mode in enumerate(MODES):
        correct={};errors={}
        for v,d in data.items():
            x=ds[v];l=x['leaders'][:,m];li=np.maximum(l,0)
            correct[v]=(l>=0)&x['primary'][li]&(x['purity'][li]>=.7)
            t=d['primary_station'][:,:,5];p=d['reco_at_primary_station'][li,:,5]
            with np.errstate(invalid='ignore',divide='ignore'):errors[v]=abs(p/t-1)
        for population,g in [('fiducial',masks['fiducial']),('accepted',masks['truth_station_acceptance']),
                             ('outside_acceptance',~masks['truth_station_acceptance'])]:
            for v,d in data.items():
                x=ds[v];c=d['raw_primary_counts'][:,m]
                for stage,p in [('primary_raw',c[:,0]>0),('primary_long',c[:,1]>0),('primary_quality',c[:,2]>0),
                                ('correct_leader',correct[v]),('final',x['final'][:,m]),('final_correct',x['final'][:,m]&correct[v])]:
                    stages.append(dict(population=population,mode=mode,version=v,stage=stage,
                        denominator=int(g.sum()),passed=int((g&p).sum())))
            for side,v,w in [('lost','old','latest'),('gained','latest','old')]:
                select=g&ds[v]['final'][:,m]&~ds[w]['final'][:,m]
                categories=np.full(len(g),'wrong_or_low_purity_old_leader',dtype='U60')
                primary=correct[v];counts=data[w]['raw_primary_counts'][:,m]
                has=ds[w]['leaders'][:,m]>=0
                categories[primary]='primary_leader_changed_or_low_purity'
                categories[primary&correct[w]]='both_correct_primary_leaders'
                categories[primary&~has]='no_long_track_any_particle'
                categories[primary&(counts[:,1]==0)&(counts[:,0]>0)]='primary_raw_only'
                categories[primary&(counts[:,0]==0)]='no_primary_raw'
                for name in np.unique(categories[select]):
                    rows.append(dict(population=population,mode=mode,migration=side,category=name,
                        events=int((select&(categories==name)).sum()),total=int(select.sum())))
                bits=ds[w]['raw'][:,m]
                first=np.argmax(~bits,axis=1)
                for label,group in [('all',select),('source_correct_primary',select&primary),
                                    ('both_correct_primary',select&primary&correct[w])]:
                    for j,cut in enumerate(cuts):
                        fail.append(dict(population=population,mode=mode,migration=side,cohort=label,
                            first_failed_cut=cut,events=int((group&(first==j)).sum()),total=int(group.sum())))
                if population=='accepted':
                    for i in np.flatnonzero(select):
                        events.append(dict(run=int(a['run'][i]),eventID=int(a['eventID'][i]),mode=mode,migration=side,
                            category=str(categories[i]),failed_cut=cuts[first[i]],
                            old_correct=bool(correct['old'][i]),latest_correct=bool(correct['latest'][i]),
                            old_pz0_gev=float(a['event_scalars'][i,m,1]),latest_pz0_gev=float(b['event_scalars'][i,m,1]),
                            old_layers=float(a['event_scalars'][i,m,2]),latest_layers=float(b['event_scalars'][i,m,2]),
                            old_ndof=float(a['event_scalars'][i,m,3]),latest_ndof=float(b['event_scalars'][i,m,3]),
                            old_chi2ndf=float(a['event_scalars'][i,m,4]),latest_chi2ndf=float(b['event_scalars'][i,m,4]),
                            truth_pz1_gev=float(a['primary_station'][i,0,5]/1000),
                            old_error1=float(errors['old'][i,0]),latest_error1=float(errors['latest'][i,0])))
                common=select&correct[v]&correct[w]
                for st in range(3):
                    x,y=errors[v][:,st],errors[w][:,st];valid=common&np.isfinite(x)&np.isfinite(y)
                    xx,yy=x[valid],y[valid]
                    accuracy.append(dict(population=population,mode=mode,migration=side,station=st+1,
                        pairs=len(xx),source_median=float(np.median(xx)) if len(xx) else np.nan,
                        destination_median=float(np.median(yy)) if len(yy) else np.nan,
                        destination_closer=int((yy<xx).sum()),source_closer=int((xx<yy).sum()),
                        source_error_lt10percent=int((xx<.1).sum()),destination_error_lt10percent=int((yy<.1).sum())))
        for v,d in data.items():
            x=ds[v];l=x['leaders'][:,m];li=np.maximum(l,0)
            for st in range(3):
                y=errors[v][:,st]
                for i in np.flatnonzero(correct[v]&x['final'][:,m]&np.isfinite(y)&(y>10)):
                    extreme.append(dict(version=v,mode=mode,station=st+1,run=int(d['run'][i]),eventID=int(d['eventID'][i]),
                        truth_accepted=bool(masks['truth_station_acceptance'][i]),relative_error=float(y[i]),
                        reco_pz_gev=float(d['reco_at_primary_station'][li[i],st,5]/1000),
                        truth_pz_gev=float(d['primary_station'][i,st,5]/1000),
                        ndof=float(x['col']['ndof'][li[i]]),chi2=float(x['col']['chi2'][li[i]]),
                        layers=float(x['col']['layers'][li[i]]),purity=float(x['purity'][li[i]])))
    for name,values in [('loss_classification',rows),('loss_first_failed',fail),('mode_stages',stages),
                        ('paired_migration_events',events),('loss_local_accuracy',accuracy),('final_extreme_tracks',extreme)]:
        table(out/(name+'.tsv'),values)
    result=dict(events=len(a['run']),accepted=int(masks['truth_station_acceptance'].sum()),
        wall_s=time.monotonic()-start,max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
