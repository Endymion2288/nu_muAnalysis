#!/usr/bin/env python3
"""Reduce targeted controls, preserving paired full-cache checks and fit lineage."""
import argparse
import gzip
import json
import math
from pathlib import Path
import resource
import tarfile
import time

import numpy as np
from compare_tracking import MODES
from report_tracking_ablation import load_cache, ordered, event_key, subset
from report_tracking_material import truth_masks
from report_tracking_station import derived, table, EVENT_KEYS, TRACK_KEYS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--manifests',type=Path,nargs='+',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();start=time.monotonic();out=args.output;out.mkdir(parents=True,exist_ok=True)
    refs={v:load_cache(args.repo/path) for v,path in [('old','workbook/stage203_station_truth/old.npz'),
        ('latest_full','workbook/stage208_master_integration/full/latest.npz')]}
    rows=[];targets=[];checks=[];resource_rows=[];significance=[];lineage=[];paired=[];completed_jobs=0
    cohorts={};cohort_checks=[];config_checks=[];actual_input_total=0
    for manifest in args.manifests:
        for job,line in enumerate(manifest.read_text().splitlines()):
            index,rdo,nevents,skip,result,control,event_ids,audit=line.split('\t')
            path=Path(result.replace('/eos/user/x/xcheng/','/eos/home-x/xcheng/'))
            if not path.exists() or not path.with_suffix('.tar.gz').exists():continue
            completed_jobs+=1
            latest=ordered(load_cache(path));ids=event_key(latest)
            cohort=(index,skip,nevents)
            cohorts.setdefault(cohort,ids)
            cohort_checks.append(bool(np.array_equal(cohorts[cohort],ids)))
            versions={v:subset(d,ids) for v,d in refs.items()};versions['control']=latest
            label=f'{manifest.parent.name}/{job:03d}'
            compare=versions['latest_full']
            for key in EVENT_KEYS+TRACK_KEYS:
                x,y=latest[key],compare[key]
                checks.append(dict(job=label,control=control,audit_library=audit,array=key,
                    exact=bool(np.array_equal(x,y,equal_nan=x.dtype.kind in 'fc'))))
            d={v:derived(a) for v,a in versions.items()};accepted=truth_masks(latest)['truth_station_acceptance']
            with np.load(path) as source:
                effective=json.loads(str(source['effective_reco_json']));perf=json.loads(str(source['performance_json']))
                actual_input_total+=int(source['counts'][0,0])
                assert effective['control']==control
                config_checks.append(bool(effective['exact_strict_map']) and
                    len(effective['algorithms'])==4 and all(
                        alg['isolated_smoothing']==(control!='shared') for alg in effective['algorithms'].values()))
                for step,value in perf.items():resource_rows.append(dict(job=label,step=step,measurement=value))
            with tarfile.open(path.with_suffix('.tar.gz')) as archive:
                raw=gzip.decompress(archive.extractfile('momentum_quality.jsonl.gz').read()).decode()
                quality={int(r[0])*1000000000+int(r[1]):r[2] for r in map(json.loads,raw.splitlines())}
                for name in archive.getnames():
                    if not name.startswith('CKF'):continue
                    for line in archive.extractfile(name):
                        r=json.loads(line);stage=r['stage']
                        if stage in ['seed','seed_override','seed_circle','selected_isolated_reference','refit_input','refit_acts_reference','converted','refit_result']:
                            lineage.append(dict(job=label,control=control,collection=name.removesuffix('.jsonl'),**r))
            for m,mode in enumerate(MODES):
                outcomes={}
                for version,a in versions.items():
                    der=d[version];leader=der['leaders'][:,m];li=np.maximum(leader,0)
                    correct=np.zeros(len(ids),dtype=bool)
                    has=leader>=0
                    correct[has]=der['primary'][li[has]]&(der['purity'][li[has]]>=.7)
                    final=der['final'][:,m]
                    t=a['primary_station'][:,0,5];p=np.full(len(ids),np.nan)
                    p[has]=a['reco_at_primary_station'][li[has],0,5]
                    with np.errstate(invalid='ignore',divide='ignore'):error=abs(p/t-1)
                    outcomes[version]=(correct,final,error)
                    selected=accepted&correct&np.isfinite(error)
                    rows.append(dict(job=label,index=index,skip=skip,nevents=nevents,control=control,audit_library=audit,
                        version=version,mode=mode,fiducial=len(ids),accepted=int(accepted.sum()),
                        primary_raw=int((accepted&(a['raw_primary_counts'][:,m,0]>0)).sum()),
                        primary_long=int((accepted&(a['raw_primary_counts'][:,m,1]>0)).sum()),
                        primary_quality=int((accepted&(a['raw_primary_counts'][:,m,2]>0)).sum()),
                        final=int((accepted&final).sum()),final_correct=int((accepted&final&correct).sum()),
                        matched_pairs=int(selected.sum()),station1_median_absolute=float(np.median(error[selected])) if selected.any() else np.nan,
                        station1_tail_gt_half=int((selected&(error>.5)).sum())))
                    if version!='control':continue
                    qsig=np.full(len(ids),np.nan)
                    if m<2:
                        for i in np.flatnonzero(leader>=0):
                            raw_index=int(der['col']['raw_index'][li[i]])
                            qsig[i]=quality[int(ids[i])][m][raw_index][2]
                        for threshold in [1,2,3]:
                            select=accepted&final&correct
                            rejected=select&(~np.isfinite(qsig)|(qsig<threshold))
                            significance.append(dict(job=label,control=control,mode=mode,threshold=threshold,
                                selected_correct_final=int(select.sum()),rejected=int(rejected.sum()),
                                selected_truth_gt1TeV=int((select&(t>1e6)).sum()),
                                selected_truth_gt3TeV=int((select&(t>3e6)).sum()),
                                selected_error_gt_half=int((select&(error>.5)).sum()),
                                rejected_truth_gt1TeV=int((rejected&(t>1e6)).sum()),
                                rejected_truth_lt1TeV=int((rejected&(t<=1e6)).sum()),
                                rejected_error_gt_half=int((rejected&(error>.5)).sum()),
                                rejected_error_lt10percent=int((rejected&(error<.1)).sum())))
                    requested={int(x) for x in event_ids.split(',')}
                    for i in np.flatnonzero(np.isin(latest['eventID'],list(requested))):
                        targets.append(dict(job=label,control=control,mode=mode,run=int(latest['run'][i]),
                            eventID=int(latest['eventID'][i]),has_long=bool(leader[i]>=0),correct=bool(correct[i]),
                            final=bool(final[i]),error1=float(error[i]) if correct[i] else np.nan,
                            pz0_gev=float(latest['event_scalars'][i,m,1]),qop_significance=float(qsig[i]),
                            raw_counts=latest['raw_primary_counts'][i,m].tolist()))
                cc,cf,ce=outcomes['control']
                for reference in ['old','latest_full']:
                    rc,rf,re=outcomes[reference]
                    common=accepted&cc&rc&np.isfinite(ce)&np.isfinite(re)
                    gained=accepted&cf&cc&~(rf&rc)
                    lost=accepted&rf&rc&~(cf&cc)
                    paired.append(dict(job=label,index=index,skip=skip,control=control,mode=mode,
                        reference=reference,accepted=int(accepted.sum()),common_correct=int(common.sum()),
                        reference_error_median=float(np.median(re[common])) if common.any() else np.nan,
                        control_error_median=float(np.median(ce[common])) if common.any() else np.nan,
                        control_closer=int((common&(ce<re)).sum()),reference_closer=int((common&(re<ce)).sum()),
                        gained_correct_final=int(gained.sum()),lost_correct_final=int(lost.sum())))
    for name,value in [('control_metrics',rows),('control_cache_checks',checks),('control_resources',resource_rows),
                       ('control_targets',targets),('qop_significance_tradeoffs',significance),
                       ('control_pair_metrics',paired)]:table(out/(name+'.tsv'),value)
    bulk=lambda r:r['job'].startswith('controls/') and str(r.get('index')) in ['0','63'] and str(r.get('skip'))=='0'
    aggregate=[];pair_aggregate=[]
    controls=['default','oldqop','oldtheta','oldseed','tightphi','shared']
    for variant in ['old','latest_full']+controls:
        for mode in MODES:
            selected=[r for r in rows if bulk(r) and r['mode']==mode and
                ((r['version']==variant and r['control']=='default') if variant in refs else
                 (r['version']=='control' and r['control']==variant))]
            if len(selected)!=2:continue
            fields=['accepted','primary_raw','primary_long','primary_quality','final','final_correct']
            aggregate.append(dict(variant=variant,mode=mode,**{k:sum(r[k] for r in selected) for k in fields}))
    for control in controls:
        for mode in MODES:
            selected=[r for r in paired if bulk(r) and r['control']==control and r['mode']==mode
                      and r['reference']=='latest_full']
            if len(selected)!=2:continue
            n=sum(r['accepted'] for r in selected)
            gained=sum(r['gained_correct_final'] for r in selected);lost=sum(r['lost_correct_final'] for r in selected)
            delta=(gained-lost)/n;se=math.sqrt(((gained+lost)/n-delta**2)/n)
            pair_aggregate.append(dict(control=control,mode=mode,accepted=n,gained_correct_final=gained,
                lost_correct_final=lost,delta_pp=100*delta,paired_normal_95_low_pp=100*(delta-1.959964*se),
                paired_normal_95_high_pp=100*(delta+1.959964*se)))
    if aggregate:table(out/'control_aggregate.tsv',aggregate)
    if pair_aggregate:table(out/'control_pair_aggregate.tsv',pair_aggregate)
    (out/'fit_lineage.json').write_text(json.dumps(lineage,indent=2)+'\n')
    immutable=['run','eventID','truth_pz_nu','truth_dec_x_nu','truth_dec_y_nu','truth_dec_z_nu',
               'primary','primary_production_momentum_mev','primary_station','primary_layer_hits','scintillator']
    record=dict(completed_jobs=completed_jobs,expected_jobs=sum(len(p.read_text().splitlines()) for p in args.manifests),
        actual_input_events_processed_with_replays=actual_input_total,
        same_cohort_ids_exact=all(cohort_checks),all_material_and_smoothing_config_exact=all(config_checks),
        immutable_arrays_exact=all(r['exact'] for r in checks if r['array'] in immutable),
        default_science_arrays_checked=sum(r['control']=='default' for r in checks),
        default_science_arrays_exact=all(r['exact'] for r in checks if r['control']=='default'),wall_s=time.monotonic()-start,
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (out/'control_summary.json').write_text(json.dumps(record,indent=2)+'\n');print(record)


if __name__=='__main__':main()
