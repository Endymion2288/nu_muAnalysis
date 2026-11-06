"""Independent stored-point checks and bounded response-support diagnostics."""
import csv
import json
import gzip
from pathlib import Path

import numpy as np

from stage122_compare import ROOT,OUT,CACHE,load,table
from stage119_curve_common import masks,weights


def check_replicas():
    d=load(CACHE/'replica_points.npz')
    parents=list(csv.DictReader((OUT/'replica_parents.tsv').open(),delimiter='\t'))
    assert len(parents)==len(d['E'])==252
    assert d['Z'].shape==d['selected'].shape==(252,16)
    checks=[]
    for j,p in enumerate(parents):
        assert int(p['selected_N'])==int(d['selected'][j].sum())
        expected=int(p['role'])>0 and p['other_cuts']=='True'
        assert bool(np.isfinite(d['Z'][j]).all())==expected
        if not expected:
            assert np.isnan(d['Z'][j]).all()
            continue
        e=d['Z'][j]-np.log(d['E'][j]);mean=float(np.sum(e)/16)
        # Independent centered sum, rather than the producer's np.var call.
        variance=float(np.sum((e-mean)**2)/16);mse=float(np.sum(e*e)/16)
        delta=max(abs(variance-float(p['output_log_variance'])),abs(mse-float(p['mean_log_MSE'])),abs(mean-float(p['mean_log_error'])),abs(mse-mean*mean-variance))
        assert delta<1e-12
        checks.append(dict(parent=j,max_abs=delta))
    risk=list(csv.DictReader((OUT/'replica_risk.tsv').open(),delimiter='\t'))
    scalar=[]
    all_weights=d['weight']*weights(d['incoming'])
    for r in risk:
        if r['environment']!='all' or r['stratum']!='all':continue
        take=np.isfinite(d['Z']).all(axis=1)
        if r['role']!='active':take&=d['role']==int(r['role'])
        z=d['Z'][take];e=z-np.log(d['E'][take,None]);w=all_weights[take]
        use=d['selected'][take] if r['condition']=='selected_realizations' else np.ones_like(e,dtype=bool)
        # Work directly in realization space, keeping parent weights /16.
        actual=float(np.sqrt(np.sum(w[:,None]*e**2*use)/np.sum(w[:,None]*use)))
        delta=abs(actual-float(r['log_RMSE']));assert delta<1e-12
        scalar.append(dict(role=r['role'],condition=r['condition'],max_abs_RMSE=delta))
    table('replica_independent_validation.tsv',checks)
    table('replica_risk_validation.tsv',scalar)
    # The historical producer's fixed array has only two VetoNu slots. When
    # secondary hits extend its container, native out-of-bounds behavior cannot
    # be certified by our safe two-primary definition. Keep every realization
    # and report selection bounds, rather than dropping these paths.
    availability=[];pos=0
    for si in range(9):
        with gzip.open(CACHE/f'replicas_{si}.json.gz','rt') as f:r=json.load(f)
        for row in r['events']:
            p=parents[pos];pos+=1;v=row['detectors']['VetoNu'];pres=row['detectors']['Preshower']
            extra=[]
            for rep in range(16):
                rec=next(q for q in v['replicas'] if q['replica']==rep)['reconstructed']
                extra.append(max(0,len(rec)-2))
            other=p['other_cuts']=='True';selected=d['selected'][pos-1]
            unknown=np.asarray(extra)>0
            known_pass=int(np.sum(selected&~unknown)) if other else 0
            unknown_N=int(unknown.sum()) if other else 0
            availability.append(dict(parent=pos-1,index=si,entry=row['entry'],role=p['role'],category=p['category'],other_cuts=other,
                VetoNu_saved_channels=len(v['saved']),VetoNu_sensitive_hits=sum(t['hits'] for t in v['timing']),Preshower_saved_channels=len(pres['saved']),
                original_extra_VetoNu_hits=max(0,len(row['original_reconstructed']['VetoNu'])-2),replica_extra_VetoNu_hits=sum(extra),secondary_views=int(unknown.sum()),
                native_selection_uncertified_views=unknown_N,native_selection_probability_lower=known_pass/16,native_selection_probability_upper=(known_pass+unknown_N)/16,
                safe_two_primary_selection_probability=float(selected.mean()),repeat_mean_minus_original_log_prediction=p.get('repeat_mean_minus_original_log_prediction','')))
    assert pos==252
    table('replica_availability_and_selection_bounds.tsv',availability)
    return dict(parent_checks=len(checks),risk_checks=len(scalar),max_parent_abs=max(r['max_abs'] for r in checks),max_risk_abs=max(r['max_abs_RMSE'] for r in scalar),quarantine_no_forward=True,distinct_parent_N=252,streams_per_parent=16,
                secondary_affected_parents=sum(r['secondary_views']>0 for r in availability),secondary_views=sum(r['secondary_views'] for r in availability),native_selection_uncertified_views=sum(r['native_selection_uncertified_views'] for r in availability),
                caveat='Replica selection/risk uses defined safe first-two-primary integrals; historical producer out-of-bounds secondary behavior is not certified. All parents retained; bounds include unknown paths.')


def main():
    from stage122_replica_analysis import qa
    qa()
    with gzip.open(CACHE/'recoqa10_0.json.gz','rt') as f:replay_a=json.load(f)
    with gzip.open(CACHE/'replaymc3_0.json.gz','rt') as f:replay_b=json.load(f)
    assert replay_a['events'][:len(replay_b['events'])]==replay_b['events'],'Cross-process replay differs'
    d=load(CACHE/'comparison_input.npz');pred=load(ROOT/'ml/artifacts/stage122/predictions.npz');checks=[]
    for r in csv.DictReader((OUT/'metrics.tsv').open(),delimiter='\t'):
        role=int(r['role']);use=(d['role']==role)&masks(d)[r['stratum']]
        w=weights(d['incoming'][d['role']==role])/d['probability'][d['role']==role];w=w[masks({k:v[d['role']==role] for k,v in d.items()})[r['stratum']]]
        err=pred[r['model']][use]-np.log(d['truth_E_GeV'][use]);actual=np.sqrt(np.average(err**2,weights=w));delta=abs(actual-float(r['log_RMSE']));assert delta<1e-12
        checks.append(dict(role=role,stratum=r['stratum'],model=r['model'],stored_RMSE_abs_difference=delta))
    initial=CACHE/'comparison_initial'
    for arm in ['A']:
        old=load(initial/f'{arm}_prediction.npz');new=load(ROOT/f'ml/artifacts/stage122/{arm}_prediction.npz')
        for k in old:np.testing.assert_array_equal(old[k],new[k])
    support=[]
    for env in ['nominal','JEFF','ENDF']:
        for role in [1,2,3]:
            for lo,hi in [(50,100),(100,200)]:
                use=(d['environment']==env)&(d['role']==role)&(d['truth_E_GeV']>=lo)&(d['truth_E_GeV']<hi)
                n=len(np.unique(d['incoming'][use],axis=0));support.append(dict(environment=env,role=role,low_GeV=lo,high_GeV=hi,N=int(use.sum()),incoming=n,required_train100_eval50=100 if role==1 else 50,gate=n>=(100 if role==1 else 50)))
    timing=[];p=json.loads((OUT/'cohort_contract.json').read_text())
    for i,s in enumerate(p['sources']):
        with gzip.open(CACHE/f'cohort_{i}.json.gz','rt') as f:r=json.load(f)
        for det in ['VetoNu','Preshower']:
            for plate in [0,1]:
                rr=[next(t for t in row['detectors'][det]['timing'] if t['plate']==plate) for row in r['events']]
                sums=np.sum([v['energy_MeV'] for v in rr],axis=0);total=float(sums.sum());inside=float(sums[1:8].sum())
                timing.append(dict(source_index=s['source_index'],environment=s['environment'],detector=det,plate=plate,parent_N=len(rr),total_sensitive_MeV=total,inside_MeV=inside,outside_fraction=(total-inside)/total if total else None,min_persisted_ns=min((v['min_time_ns'] for v in rr if v['min_time_ns'] is not None),default=None),max_persisted_ns=max((v['max_time_ns'] for v in rr if v['max_time_ns'] is not None),default=None)))
    table('stored_point_validation.tsv',checks);table('environment_support.tsv',support);table('persisted_time_coverage.tsv',timing)
    report=dict(cross_process_replay_parents=len(replay_b['events']),full_ADC_before_after_state_equal=True,stored_point_checks=len(checks),max_abs_RMSE_difference=max(r['stored_RMSE_abs_difference'] for r in checks),A_original_feature_prediction_array_equal=True,environment_2x2_gate=all(v['gate'] for v in support),replica_independent_checks=check_replicas(),producer_G4_termination_certified=False,full_GENIE_replay_input_certified=False,real_data_MC_ADC_calibration_closed=False)
    (OUT/'final_validation.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)


if __name__=='__main__':main()
