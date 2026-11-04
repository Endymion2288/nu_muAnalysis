"""Stage95 compact-table physics diagnostics and independent relation checks; no fit."""
import csv
import json
import math
import resource
import time
from pathlib import Path

import numpy as np
from track_candidate_information import REPO, OUT, CACHE, SEED, save, table, cost


def read(name):
    return list(csv.DictReader((CACHE / name).open(),delimiter='\t'))


def number(r,k):return float(r[k])


def main():
    start=time.perf_counter(),time.process_time()
    plan=json.loads((CACHE/'cohort.json').read_text());records=plan['records'];metadata={r['row']:r for r in records}
    events=read('events.tsv');candidates=read('candidates.tsv');edges=read('relations.tsv');labels=read('truth_diagnostics.tsv')
    expected_N=plan['N'];assert len(events)==len(metadata)==len({r['key_id'] for r in records})==expected_N
    assert {int(r['row']) for r in events}==set(metadata)
    assert all(r['role'] in [1,2] for r in records)
    ids=np.array([int(r['row']) for r in events]);lookup={int(r['row']):i for i,r in enumerate(events)};available=np.array([r['available']=='True' for r in events])
    nodegroups={int(r):[] for r in ids};edgegroups={int(r):[] for r in ids};labelgroups={int(r):[] for r in ids}
    for r in candidates:nodegroups[int(r['row'])].append(r)
    for r in edges:edgegroups[int(r['row'])].append(r)
    for r in labels:labelgroups[int(r['row'])].append(r)
    checks=0;max_pz_delta=0.;max_oracle_delta=0.
    for event in events:
        row=int(event['row']);nodes=nodegroups[row];relations=edgegroups[row];ll=labelgroups[row]
        if event['available']!='True':assert not nodes and not relations and not ll;continue
        n=int(event['n_tracks']);assert len(nodes)==len(ll)==n and len(relations)==n*(n-1)//2
        lead=int(event['lead_index']);assert sum(v['leading']=='True' for v in nodes)==1
        pts=np.array([number(v,'pz0_GeV') for v in nodes]);assert np.nanargmax(pts)==lead
        delta=abs(pts[lead]-metadata[row]['pz_GeV']);max_pz_delta=max(max_pz_delta,delta);assert delta<2e-4
        conf=np.array([v['primary_confirmed']=='True' for v in ll]);assert bool(conf[lead])==(event['lead_primary_confirmed']=='True') and bool(conf.any())==(event['any_primary_confirmed']=='True')
        target=number(event,'primary_truth_pz_GeV');errs=abs(np.log(pts[conf]/target));expected=float(np.nanmin(errs)) if len(errs) else np.nan;observed=number(event,'matched_candidate_oracle_abs_log_error')
        if np.isfinite(expected):max_oracle_delta=max(max_oracle_delta,abs(expected-observed));assert abs(expected-observed)<1e-12
        else:assert np.isnan(observed)
        for edge in relations:
            a,b=[nodes[int(edge[k])] for k in ['track_i','track_j']]
            for x,y,k in [('x0_mm','y0_mm','delta_x0_y0_mm'),('calo_x_mm','calo_y_mm','delta_calo_mm'),('veto_x_mm','veto_y_mm','delta_veto_mm')]:
                expected=math.sqrt((number(a,x)-number(b,x))**2+(number(a,y)-number(b,y))**2);observed=number(edge,k)
                assert np.isclose(expected,observed,atol=1e-10,rtol=1e-12,equal_nan=True);checks+=1
    # Fixed-source and observed-X quota conditional bootstrap, one incoming per record.
    rng=np.random.default_rng(SEED);draw=np.zeros((500,len(events)),dtype=np.int16);buckets={}
    for i,row in enumerate(ids):
        r=metadata[int(row)];buckets.setdefault((r['source'],r['pz_GeV']<100,r['status_other']),[]).append(i)
    for values in buckets.values():
        n=len(values);draw[:,values]=rng.multinomial(n,np.full(n,1/n),size=500)
    pz=np.array([metadata[int(r)]['pz_GeV'] for r in ids]);comp=np.array([metadata[int(r)]['component'] for r in ids]);role=np.array([metadata[int(r)]['role'] for r in ids]);source=np.array([metadata[int(r)]['source'] for r in ids])
    def field(k):return np.array([number(r,k) for r in events])
    ntracks=field('n_tracks');npairs=field('n_pairs');energy=np.array([metadata[int(r)]['reference_truth_E_GeV'] for r in ids]);y=np.array([metadata[int(r)]['reference_y_lepton'] for r in ids])
    lead=np.array([r['lead_primary_confirmed']=='True' for r in events]);anymatch=np.array([r['any_primary_confirmed']=='True' for r in events]);recovered=~lead&anymatch&available
    masks=dict(all=np.ones(len(ids),bool),train=role==1,cal=role==2,X_pz50_100=pz<100,X_pz100_plus=pz>=100,X_status_other=np.array([metadata[int(r)]['status_other'] for r in ids]),input_missing=np.array([metadata[int(r)]['input_missing'] for r in ids]),E50_100=(energy>=50)&(energy<100),E100_200=(energy>=100)&(energy<200),low_pz_trueE200=(pz<100)&(energy>=200),high_y=y>=.8,leading_unconfirmed=np.array([not metadata[int(r)]['reference_confirmed'] for r in ids]),multitrack=available&(ntracks>1))
    for c in ['pi','k','charm']:masks[c]=comp==c
    for s in sorted(set(source)):masks['source_'+s]=source==s
    rows=[];intervals=[]
    for name,mask in masks.items():
        use=mask&available;n=int(use.sum());t=int(mask.sum());nodes=int(np.nansum(ntracks[use]));pairs=int(np.nansum(npairs[use]));q=np.quantile(ntracks[use],[.5,.9,1]) if n else [np.nan]*3
        flags=dict(multitrack=(ntracks>1)&available,leading_unconfirmed=available&~lead,any_primary_confirmed=available&anymatch,recovered_primary=recovered,primary_multi_candidates=field('primary_confirmed_tracks')>1,hitset_length_mismatch=available&np.isfinite(field('hitset_length'))&(field('hitset_length')!=ntracks),distinct_calo=field('distinct_calo_pairs')>0,geometric_near=field('geometric_near_pairs')>0)
        row=dict(scope=name,requested_N=t,available_N=n,unavailable_N=t-n,sources=len(set(source[mask])),candidate_tracks=nodes,pairs=pairs,median_tracks=q[0],p90_tracks=q[1],max_tracks=q[2],finite_calo_tracks=int(np.nansum(field('finite_calo_tracks')[use])),finite_veto_tracks=int(np.nansum(field('finite_veto_tracks')[use])),finite_timing_tracks=int(np.nansum(field('finite_timing_tracks')[use])),valid_station_tracks=int(np.nansum(field('valid_station_tracks')[use])),three_downstream_tracks=int(np.nansum(field('three_downstream_tracks')[use])),invalid_module_tracks=int(np.nansum(field('invalid_module_tracks')[use])),raw_invalid_channels=int(np.nansum(field('raw_invalid_channels')[use])),valid_negative_raw_channels=int(np.nansum(field('valid_negative_raw_channels')[use])),truth_hitratio_out_of_range=int(np.nansum(field('truth_hitratio_out_of_range')[use])),shared_hit_rate='未测量',true_duplicate_rate='未测量',sparse=n<20)
        den=draw@use.astype(float);good=den>0
        for key,flag in flags.items():
            count=int((flag&use).sum());value=100*count/n if n else np.nan;row[key+'_N']=count;row[key+'_pct']=value
            if n:
                bs=(draw@(flag&use).astype(float))[good]/den[good]*100;ci=np.quantile(bs,[.025,.975]);intervals.append(dict(scope=name,metric=key,N=n,count=count,pct=value,conditional_low95_pct=float(ci[0]),conditional_high95_pct=float(ci[1]),valid_draws=int(good.sum()),source95='未测量',scope_note='one incoming/view; fixed source and X quota conditional, no parent/source/production-systematic coverage'))
        rows.append(row)
    table('profiles.tsv',rows);table('conditional_intervals.tsv',intervals)
    # Observed opportunity for primary association recovery; no event selection by oracle.
    recovered_rows=[]
    for i in np.flatnonzero(recovered):
        r=metadata[int(ids[i])];recovered_rows.append(dict(row=int(ids[i]),source=r['source'],role=r['role'],component=r['component'],pz_GeV=r['pz_GeV'],truth_E_GeV=float(energy[i]),y_lepton=float(y[i]),n_tracks=int(ntracks[i])))
    # Individual diagnostics are data artifacts, not a population claim or model inputs.
    if recovered_rows:
        with (CACHE/'recovered_primary.tsv').open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(recovered_rows[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(recovered_rows)
    primary_subset=available&anymatch;leaderr=field('lead_mu_log_error');oracle=field('matched_candidate_oracle_abs_log_error');op=primary_subset&np.isfinite(leaderr)&np.isfinite(oracle)
    oracle_summary=dict(matched_primary_subset_N=int(op.sum()),lead_mu_pz_log_RMSE=float(np.sqrt(np.mean(leaderr[op]**2))),truth_matched_candidate_oracle_mu_pz_log_RMSE=float(np.sqrt(np.mean(oracle[op]**2))),improved_incoming_N=int((op&(oracle<abs(leaderr)-1e-12)).sum()),neutrino_energy_oracle='未测量; muon pz target is not E_nu, true labels cannot be deployed')
    save('oracle_diagnostic.json',oracle_summary)
    save('validation.json',dict(passed=True,events=expected_N,available_events=int(available.sum()),candidate_rows=len(candidates),pair_rows=len(edges),independent_distance_checks=checks,max_leading_pz_delta_GeV=max_pz_delta,max_oracle_log_difference=max_oracle_delta,identity_and_roles_checked=True,raw_input_truth_key_checks='extractor exact native-MeV four-vector/run/event/source-entry',one_incoming_one_view=True,test_event_payloads=0,new_fits=0,**cost(start)))
    # Fixed minimal input contract: candidate nodes plus leading-relative geometric edges.
    deploy=list(candidates[0]);deploy=[k for k in deploy if k not in ['row','track_index','leading']]
    save('representation.json',dict(name='track_candidates_leading_geometry_v1',candidate_features=deploy,candidate_order='decreasing finite pz0, stable original index ties; invalid pz0 retained with missing mask',candidate_truncation=None,leading_index='same argmax pz0 used in audited62',edge_features=['delta_x0_y0_mm','delta_calo_mm','delta_veto_mm','delta_slope','same_charge'],edge_topology='leading-to-all-other; full pair table retained for diagnostics only',charge_missing='both charges must be valid before interpreting equality',hitset_input=False,shared_hit_edges=False,truth_inputs=False,nonphysical_placeholders='typed NaN, separate missing masks; empty collection != unavailable source',pz0_only_first_power=True,no_energy_fit_this_stage=True))
    plot(rows)
    child=resource.getrusage(resource.RUSAGE_CHILDREN)
    save('report_completion.json',dict(passed=True,profile_rows=len(rows),conditional_interval_rows=len(intervals),bootstrap_repeats=500,new_fits=0,independent_energy_gain='未测量',child_CPU_s=child.ru_utime+child.ru_stime,**cost(start)))
    print(json.dumps(next(r for r in rows if r['scope']=='all')),flush=True)


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(1,2,figsize=(11,4),layout='constrained');groups=['all','pi','k','charm','X_pz50_100','low_pz_trueE200','high_y'];rr=[next(r for r in rows if r['scope']==g) for g in groups];x=np.arange(len(groups))
    for j,key in enumerate(['multitrack_pct','leading_unconfirmed_pct','recovered_primary_pct']):ax[0].bar(x+(j-1)*.24,[r[key] for r in rr],width=.24,label=key.replace('_pct',''))
    ax[0].set(xticks=x,xticklabels=groups,ylabel='Fraction of available incoming (%)',title='Fixed diagnostic cohort: not natural flux');ax[0].tick_params(axis='x',rotation=35);ax[0].legend(fontsize=8)
    for j,key in enumerate(['finite_calo_tracks','finite_veto_tracks','valid_station_tracks']):ax[1].bar(x+(j-1)*.24,[100*r[key]/r['candidate_tracks'] if r['candidate_tracks'] else np.nan for r in rr],width=.24,label=key)
    ax[1].set(xticks=x,xticklabels=groups,ylabel='Fraction of candidate tracks (%)',ylim=(0,105),title='Deployable payload availability');ax[1].tick_params(axis='x',rotation=35);ax[1].legend(fontsize=8)
    for a in ax:a.grid(axis='y',alpha=.2)
    path=OUT/'candidate_information.svg';fig.savefig(path);path.write_text('\n'.join(s.rstrip() for s in path.read_text().splitlines())+'\n');plt.close(fig)


if __name__=='__main__':main()
