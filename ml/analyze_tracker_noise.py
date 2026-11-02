#!/usr/bin/env python3
"""Validate the frozen replay gate and summarize paired conditional responses."""
import argparse
import csv
import json
import math
from collections import Counter
import tarfile
import time
import resource
from pathlib import Path

import numpy as np

NAMES = ['nClusters0','nClusters1','nClusters2','nClusters3','SpacePoints','TrackSegments']
THRESHOLDS = np.array([6,6,6,6,12,4])


def read_result(directory, name):
    path = directory/name
    if path.is_file():
        return json.loads(path.read_text())
    with tarfile.open(directory/'replay_results.tar.gz') as archive:
        return json.load(archive.extractfile(name))


def counts(record, label):
    return record['clusters'][label]+[record['spacepoints'][label],record['segments'][label]]


def selection_failures(record, case):
    tracks = record['tracks']['Replay']
    if len(tracks) != 1:
        return ['no_long_track' if not tracks else 'multiple_long_tracks']
    p,pz,layers,ndof,chi2,q,x,y,tx,ty,xt,yt = tracks[0]
    checks = dict(layers=layers>=7, ndof=ndof>=9, fit_quality=ndof>0 and chi2/ndof<15,
                  momentum=100000<=p<1000000, upstream_xy=abs(x)<500 and abs(y)<500,
                  upstream_angle=math.hypot(tx,ty)<.025, veto_tag=all(v>40 for v in case['veto_raw_pC']),
                  timing_xy=abs(xt)<80 and abs(yt)<80, unit_charge=abs(q)==1)
    return [k for k,v in checks.items() if not v]


def read_nominal(directory, sample):
    rows, sources, cases, files = [], [], [], []
    for source in sample['sources']:
        result = read_result(directory,f'nominal_{source["source"]}.json')
        assert result['mode']=='nominal' and result['frontend']['NoiseOn']=='True'
        assert result['input']==source['input_rdo']
        assert result['requested_entries']==[c['entry'] for c in source['cases']]
        assert len(result['records']) == len(source['cases'])
        files.append(result)
        for record, case in zip(result['records'],source['cases']):
            assert (record['entry'],record['event'],record['run']) == (case['entry'],case['event'],source['run'])
            rows.append(record); sources.append(source['source']); cases.append(case)
    return rows, np.array(sources), cases, files


def gate_summary(rows, sources, cases, files):
    checks = {
        'rdo_p4_exact': [r['rdo_p4_exact_equal'] for r in rows],
        'reference_p4_idempotent': [r['reference_p4_idempotent'] for r in rows],
        'reference_original_counts': [counts(r,'Reference') == c['original_counts'] for r,c in zip(rows,cases)],
        'replay_reference_counts': [counts(r,'Replay') == counts(r,'Reference') for r in rows],
        'reference_original_selection': [r['selected']['Reference'] for r in rows],
        'replay_original_selection': [r['selected']['Replay'] for r in rows],
        'nominal_reference_track_exact': [r['tracks']['Reference']==r['tracks']['Replay'] for r in rows],
    }
    failures = {k:int(np.sum(~np.asarray(v))) for k,v in checks.items()}
    track_delta = []
    for r,c in zip(rows,cases):
        tracks = r['tracks']['Reference']
        if len(tracks)==1:
            track_delta.append(np.array(tracks[0])-np.array(c['track']))
    delta = np.array(track_delta)
    original_p = np.array([c['track'][0] for r,c in zip(rows,cases) if len(r['tracks']['Reference'])==1])
    p_rel = delta[:,0]/original_p
    return dict(events=len(rows),sources=len(np.unique(sources)),passed=not any(failures.values()),
        failures=failures,source_failures={str(s):{k:int(np.sum(~np.asarray(v)[sources==s])) for k,v in checks.items()} for s in np.unique(sources)},
        legacy_track_comparison=dict(single_tracks=len(delta),relative_p_quantiles=np.quantile(p_rel,[0,.16,.5,.84,1]).tolist(),
            abs_max_delta_by_column=np.max(abs(delta),axis=0).tolist(),columns=['p_MeV','pz_MeV','nLayers','nDoF','Chi2','charge','X_atVetoNu_mm','Y_atVetoNu_mm','ThetaX_rad','ThetaY_rad','X_atTrig_mm','Y_atTrig_mm']),
        replay_wall_s=sum(f['wall_s'] for f in files),replay_cpu_s=sum(f['cpu_s'] for f in files),
        peak_rss_MiB=max(f['peak_rss_MiB'] for f in files),ROOT_all_files_bytes_read=sum(f['root_all_files_bytes_read'] for f in files))


def bootstrap_indices(sources, mask):
    ids = np.unique(sources[mask]); rng=np.random.default_rng(2026110254)
    if len(ids)<2:
        return []
    blocks = {s:np.flatnonzero(mask & (sources==s)) for s in ids}
    result=[]
    for _ in range(500):
        picked=[]
        for sign in [0,1]:
            pool=ids[(ids>=6)==bool(sign)]
            if len(pool):
                picked.extend(rng.choice(pool,len(pool),replace=True))
        result.append(np.concatenate([blocks[s] for s in picked]))
    return result


def nominal_tables(output, rows, sources, cases):
    original=np.array([c['original_counts'] for c in cases])
    replay=np.array([counts(r,'Replay') for r in rows])
    pbin=np.array([c['pbin'] for c in cases])
    groups=[('all',np.ones(len(rows),bool)),('p100_250',pbin==0),('p250_1000',pbin==1),
            ('mu_minus',sources<6),('mu_plus',sources>=6)]
    groups += [(f'source{s}',sources==s) for s in range(12)]
    flags={'rdo_mismatch':np.array([not r['rdo_p4_exact_equal'] for r in rows]),
           'count_mismatch':np.any(original!=replay,axis=1),
           'reference_selection_fail':np.array([not r['selected']['Reference'] for r in rows]),
           'replay_selection_fail':np.array([not r['selected']['Replay'] for r in rows])}
    table=[];rates=[]
    for label,mask in groups:
        boots=bootstrap_indices(sources,mask)
        for name,values in flags.items():
            ci=(100*np.quantile([values[b].mean() for b in boots],[.025,.975])).tolist() if boots else [None,None]
            rates.append(dict(group=label,check=name,N=int(mask.sum()),failed=int(values[mask].sum()),
                              percent=float(100*values[mask].mean()),low=ci[0],high=ci[1]))
        for j,name in enumerate(NAMES):
            delta=replay[:,j]-original[:,j]
            extra=(replay[:,j]>THRESHOLDS[j]).astype(float)-(original[:,j]>THRESHOLDS[j]).astype(float)
            ci=np.quantile([delta[b].mean() for b in boots],[.025,.975]).tolist() if boots else [None,None]
            eci=(100*np.quantile([extra[b].mean() for b in boots],[.025,.975])).tolist() if boots else [None,None]
            table.append(dict(group=label,variable=name,N=int(mask.sum()),
                original_mean=float(original[mask,j].mean()),replay_mean=float(replay[mask,j].mean()),
                delta_mean=float(delta[mask].mean()),low=ci[0],high=ci[1],
                original_extra_pct=float(100*np.mean(original[mask,j]>THRESHOLDS[j])),
                replay_extra_pct=float(100*np.mean(replay[mask,j]>THRESHOLDS[j])),
                delta_extra_pp=float(100*extra[mask].mean()),extra_low=eci[0],extra_high=eci[1],
                changed=int(np.sum(delta[mask]!=0)),max_abs_count_delta=int(np.max(abs(delta[mask])))))
    for name,data in [('nominal_response.tsv',table),('nominal_failure_rates.tsv',rates)]:
        with (output/name).open('w') as file:
            writer=csv.DictWriter(file,fieldnames=list(data[0]),delimiter='\t',lineterminator='\n')
            writer.writeheader()
            writer.writerows({k:('NA' if v is None else v) for k,v in row.items()} for row in data)
    failures=[]
    for r,s,c in zip(rows,sources,cases):
        if not r['rdo_p4_exact_equal'] or not r['selected']['Reference']:
            failures.append(dict(source=int(s),entry=r['entry'],event=r['event'],pbin=c['pbin'],
                original_p_GeV=c['track'][0]/1000,rdo_equal=r['rdo_p4_exact_equal'],
                original_counts=c['original_counts'],replay_counts=counts(r,'Replay'),
                reference_selected=r['selected']['Reference'],replay_selected=r['selected']['Replay'],
                original_track=c['track'],reference_tracks=r['tracks']['Reference'],replay_tracks=r['tracks']['Replay']))
    (output/'nominal_failure_cases.json').write_text(json.dumps(failures,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(8,4))
    x=np.arange(5)
    for offset,check,label in [(-.16,'rdo_mismatch','RDO mismatch'),(.16,'reference_selection_fail','Selection migration')]:
        data=[r for r in rates if r['group'] in ['all','p100_250','p250_1000','mu_minus','mu_plus'] and r['check']==check]
        y=np.array([r['percent'] for r in data])
        errors=np.array([[r['low'] for r in data],[r['high'] for r in data]])
        ax.bar(x+offset,y,.32,label=label)
        ax.errorbar(x+offset,y,yerr=np.vstack([y-errors[0],errors[1]-y]),fmt='none',color='black',capsize=3)
    ax.set_xticks(x,['All','100–250 GeV','250–1000 GeV','μ−','μ+'])
    ax.set_ylabel('Nominal replay failure (%)');ax.set_title('2048 fixed muons; 95% paired source bootstrap intervals')
    ax.legend();fig.tight_layout();fig.savefig(output/'nominal_replay_failures.png',dpi=150);plt.close(fig)
    return rates[:20],table[:30]


def main():
    start,cpu = time.perf_counter(),time.process_time()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=Path('ntuples/energy_ml_stage53'))
    parser.add_argument('--output',type=Path,default=Path('workbook/stage53_energy_ml'))
    parser.add_argument('--nominal-only',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    sample=read_result(args.directory,'sample.json')
    rows,sources,cases,nominal_files=read_nominal(args.directory,sample)
    gate=gate_summary(rows,sources,cases,nominal_files)
    gate['stratified_rates'],gate['stratified_response']=nominal_tables(args.output,rows,sources,cases)
    (args.output/'nominal_validation.json').write_text(json.dumps(gate,indent=2)+'\n')
    print(json.dumps({k:v for k,v in gate.items() if not k.startswith('stratified_')}),flush=True)
    if args.nominal_only:
        return
    assert gate['passed'],'Frozen nominal gate failed; noise causal comparison is prohibited'
    off=[];off_files=[]
    for s in sample['sources']:
        f=read_result(args.directory,f'nonoise_{s["source"]}.json');off_files.append(f)
        assert f['mode']=='nonoise' and f['input']==s['input_rdo']
        assert f['requested_entries']==[c['entry'] for c in s['cases']]
        assert len(f['records'])==len(s['cases'])
        assert f['frontend']==dict(nominal_files[s['source']]['frontend'],NoiseOn='False')
        assert f['material_source']==nominal_files[s['source']]['material_source']
        assert f['original_hits_diagnostic'] and nominal_files[s['source']]['original_hits_diagnostic']
        off.extend(f['records'])
    for n,o in zip(rows,off):
        assert (n['run'],n['event'],n['entry'])==(o['run'],o['event'],o['entry'])
        assert counts(n,'Reference')==counts(o,'Reference')
        assert n['tracks']['Reference']==o['tracks']['Reference']
    on=np.array([counts(r,'Replay') for r in rows]); no=np.array([counts(r,'Replay') for r in off])
    pbin=np.array([c['pbin'] for c in cases])
    sel_on=np.array([r['selected']['Replay'] for r in rows]);sel_off=np.array([r['selected']['Replay'] for r in off])
    groups=[('all',np.ones(len(rows),bool)),('p100_250',pbin==0),('p250_1000',pbin==1),('mu_minus',sources<6),('mu_plus',sources>=6)]
    groups += [(f'source{s}',sources==s) for s in range(12)]
    groups += [(f'source{s}_p{b}',(sources==s)&(pbin==b)) for s in range(12) for b in [0,1]]
    failure_cases=[]
    for s,n,o,c in zip(sources,rows,off,cases):
        reasons=selection_failures(o,c)
        assert o['selected']['Replay']==(not reasons)
        if reasons:
            failure_cases.append(dict(source=int(s),entry=o['entry'],event=o['event'],pbin=c['pbin'],
                nominal_p_GeV=c['track'][0]/1000,reasons=reasons,off_tracks=o['tracks']['Replay']))
    (args.output/'selection_failure_cases.json').write_text(json.dumps(failure_cases,indent=2)+'\n')
    table=[];migration=[]
    for label,mask in groups:
        indices=np.flatnonzero(mask);boots=bootstrap_indices(sources,mask)
        loss=(sel_on & ~sel_off).astype(float)
        loss_ci=(100*np.quantile([loss[b].mean() for b in boots],[.025,.975])).tolist() if boots else [None,None]
        migration.append(dict(group=label,N=len(indices),sources=len(np.unique(sources[mask])),
            pass_to_pass=int(np.sum(mask&sel_on&sel_off)),pass_to_fail=int(np.sum(mask&sel_on&~sel_off)),
            fail_to_pass=int(np.sum(mask&~sel_on&sel_off)),fail_to_fail=int(np.sum(mask&~sel_on&~sel_off)),
            loss_pct=float(100*loss[mask].mean()),loss_low=loss_ci[0],loss_high=loss_ci[1]))
        for j,name in enumerate(NAMES):
            x,y=on[mask,j],no[mask,j]
            delta=no[:,j]-on[:,j]
            extra=(no[:,j]>THRESHOLDS[j]).astype(float)-(on[:,j]>THRESHOLDS[j]).astype(float)
            mean_ci=np.quantile([delta[b].mean() for b in boots],[.025,.975]).tolist() if boots else [None,None]
            rate_ci=(100*np.quantile([extra[b].mean() for b in boots],[.025,.975])).tolist() if boots else [None,None]
            qx=np.quantile(x,[.16,.5,.84,.95,.99]);qy=np.quantile(y,[.16,.5,.84,.95,.99])
            table.append(dict(group=label,variable=name,N=len(x),sources=len(np.unique(sources[mask])),
                nominal_mean=float(x.mean()),nonoise_mean=float(y.mean()),delta_mean=float((y-x).mean()),
                delta_mean_low=mean_ci[0],delta_mean_high=mean_ci[1],
                nominal_extra_pct=float(100*np.mean(x>THRESHOLDS[j])),nonoise_extra_pct=float(100*np.mean(y>THRESHOLDS[j])),
                delta_extra_pp=float(100*np.mean(extra[mask])),delta_extra_low=rate_ci[0],delta_extra_high=rate_ci[1],
                **{f'nominal_q{q}':float(v) for q,v in zip([16,50,84,95,99],qx)},
                **{f'nonoise_q{q}':float(v) for q,v in zip([16,50,84,95,99],qy)},
                same=int(np.sum(x==y)),decreased=int(np.sum(y<x)),increased=int(np.sum(y>x))))
    for filename,data in [('paired_response.tsv',table),('selection_migration.tsv',migration)]:
        with (args.output/filename).open('w') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]),delimiter='\t',lineterminator='\n')
            writer.writeheader()
            writer.writerows({k:('NA' if v is None else v) for k,v in row.items()} for row in data)
    summary=dict(events=len(rows),unit_weight=True,source_bootstraps=500,bootstrap_strata='mu sign',
        rdo_changed_events=sum(not r['rdo_p4_exact_equal'] for r in off),
        selection_failure_reasons=dict(Counter(reason for c in failure_cases for reason in c['reasons'])),
        main=[r for r in table if r['group'] in ['all','p100_250','p250_1000','mu_minus','mu_plus']],
        selection=[r for r in migration if r['group'] in ['all','p100_250','p250_1000','mu_minus','mu_plus']],
        off_wall_s=sum(f['wall_s'] for f in off_files),off_cpu_s=sum(f['cpu_s'] for f in off_files),
        off_peak_rss_MiB=max(f['peak_rss_MiB'] for f in off_files),
        off_ROOT_all_files_bytes_read=sum(f['root_all_files_bytes_read'] for f in off_files))
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    main=summary['main'][:6];x=np.arange(6)
    fig,(ax,paired)=plt.subplots(2,1,figsize=(9,6),sharex=True)
    ax.bar(x-.17,[r['nominal_extra_pct'] for r in main],.34,label='Nominal')
    ax.bar(x+.17,[r['nonoise_extra_pct'] for r in main],.34,label='NoiseOn=False')
    ax.set_ylabel('Extra activity (%)');ax.set_title('Same 2048 selected muons; fixed source / momentum mixture')
    ax.legend()
    delta=np.array([r['delta_extra_pp'] for r in main])
    low=np.array([r['delta_extra_low'] for r in main]);high=np.array([r['delta_extra_high'] for r in main])
    paired.errorbar(x,delta,yerr=np.vstack([delta-low,high-delta]),fmt='o',capsize=4)
    paired.axhline(0,color='gray',linewidth=1)
    paired.set_xticks(x,[f'C{i}>6' for i in range(4)]+['SP>12','Segments>4'])
    paired.set_ylabel('Off − nominal (pp)')
    paired.set_title('95% paired source intervals; stratified by muon sign',fontsize=10)
    fig.tight_layout();fig.savefig(args.output/'paired_extra_activity.png',dpi=150);plt.close(fig)
    (args.output/'analysis_resources.json').write_text(json.dumps(dict(
        wall_s=time.perf_counter()-start,cpu_s=time.process_time()-cpu,
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024),indent=2)+'\n')


if __name__=='__main__':
    main()
