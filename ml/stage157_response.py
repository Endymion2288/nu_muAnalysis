"""Two frozen joint response arms, evaluated only on batch-native controls."""
import csv
import json
import math
import resource
import time
from pathlib import Path
import numpy as np

OUT=Path('workbook/stage157_energy_ml')
CHANNELS=['VetoNu0','VetoNu1','Veto10','Veto20','Veto21','Timing0','Timing1','Timing2','Timing3','Preshower0','Preshower1']+[f'Calo{i}' for i in range(4)]

def clean(values):
    result = np.asarray(values, dtype=float).copy()
    result[~np.isfinite(result) | np.isin(result, [-999., -9999., -99999.])] = np.nan
    return result

def wilson(k, n):
    if n == 0:
        return None, None
    z = 1.959963984540054
    p = k/n
    denominator = 1+z*z/n
    centre = (p+z*z/(2*n))/denominator
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return centre-half, centre+half

def evaluate(index, data, report):
    rows, models = [], {}
    if data is None:
        return rows, models
    entry, point = data['entry'], data['point']
    split = entry % 4
    fit, calibration, test = split < 2, split == 2, split == 3
    for policy in ['Q15', 'Q15G6']:
        y = np.arcsinh(data['charge'])
        if policy == 'Q15G6':
            y = np.column_stack([y, data['geometry']])
        available = np.all(np.isfinite(point), axis=1) & np.all(np.isfinite(y), axis=1)
        train = fit & available
        base = dict(source_index=index, policy=policy, fit_N=int(train.sum()),
                    selected_N=len(entry), missing_readout_or_state_N=int((~available).sum()),
                    dimension=y.shape[1])
        if train.sum() < y.shape[1]+10:
            models[policy] = dict(base, supported=False, reason='Too few complete fit controls; no feature dropping or imputation')
            continue
        lo, hi = point[train].min(axis=0), point[train].max(axis=0)
        in_range = np.all((point >= lo) & (point <= hi), axis=1)
        mean, sd = point[train].mean(axis=0), point[train].std(axis=0)
        sd[sd == 0] = 1
        design = np.column_stack([np.ones(len(point)), (point-mean)/sd])
        beta, _, rank, singular = np.linalg.lstsq(design[train], y[train], rcond=None)
        residual = y-design@beta
        covariance = np.atleast_2d(np.cov(residual[train], rowvar=False))
        sigma = .9*covariance+.1*np.diag(np.diag(covariance))
        eigen = np.linalg.eigvalsh(sigma)
        if eigen[0] <= 0:
            models[policy] = dict(base, supported=False, reason='Singular measured response covariance; no extra regularization scan', eigenvalues=eigen.tolist())
            continue
        inverse = np.linalg.inv(sigma)
        score = np.einsum('ni,ij,nj->n', residual, inverse, residual)
        score_check_rows = np.flatnonzero(available)[:64]
        whitening = np.linalg.solve(np.linalg.cholesky(sigma), residual[score_check_rows].T)
        independent_score = np.sum(whitening**2, axis=0)
        assert np.allclose(independent_score, score[score_check_rows], rtol=1e-8, atol=1e-8)
        cal = calibration & available & in_range
        ncal = int(cal.sum())
        k = math.ceil(.95*(ncal+1))
        if ncal < 25 or k > ncal:
            models[policy] = dict(base, supported=False, reason='Too few in-support calibration controls', calibration_N=ncal)
            continue
        threshold = float(np.sort(score[cal])[k-1])
        total_charge = data['charge'].sum(axis=1)
        tail_threshold = float(np.quantile(total_charge[train], .99))
        overflow = np.any((data['status'] & 4) != 0, axis=1)
        groups = dict(all=np.ones(len(entry), bool), overflow=overflow,
                      high_activity=total_charge > tail_threshold,
                      pz50_100=(data['pz'] >= 50) & (data['pz'] < 100))
        for group, mask in groups.items():
            denominator = test & mask
            use = denominator & available & in_range
            n = int(use.sum())
            alerts = int(np.count_nonzero((score > threshold) & use))
            low, high = wilson(alerts, n)
            pure = report['MC_truth_mu_only_N'] == report['selected_muon_N'] and report['source']['kind'].startswith('MC')
            rows.append(dict(source_index=index, policy=policy, group=group,
                             original_heldout_N=int(denominator.sum()), scored_N=n, alerts=alerts,
                             alert_fraction=alerts/n if n else None, Wilson95_low=low, Wilson95_high=high,
                             missing_N=int(np.count_nonzero(denominator & ~available)),
                             outside_fit_state_range_N=int(np.count_nonzero(denominator & available & ~in_range)),
                             interpretation='mu-only MC empirical false alarm fraction' if pure else 'control alert fraction, not certified false positive rate'))
        models[policy] = dict(base, supported=True, calibration_N=ncal, design_rank=int(rank),
                              design_columns=design.shape[1], design_singular_values=singular.tolist(),
                              state_mean=mean.tolist(), state_scale=sd.tolist(), state_lo=lo.tolist(), state_hi=hi.tolist(),
                              beta=beta.tolist(), covariance=sigma.tolist(), covariance_min_eigenvalue=float(eigen[0]),
                              threshold=threshold, conformal_order_statistic=k,
                              independent_score_check_N=len(score_check_rows),
                              independent_score_max_abs_delta=float(np.max(abs(independent_score-score[score_check_rows]))),
                              high_activity_train_sum_raw_charge99_pC=tail_threshold,
                              max_abs_offdiagonal_correlation=float(np.max(np.abs(covariance/np.sqrt(np.outer(np.diag(covariance), np.diag(covariance)))-np.eye(y.shape[1])))),
                              support='Point conditioning; stored track covariance not a calibrated error; original verified muon-root file, development split not independent source/data confirmation')
    return rows, models


def run(native,pairs):
    tick,cpu=time.perf_counter(),time.process_time()
    selected=[i for i,p in enumerate(pairs) if p['new_selected']]
    point=[];charge=[];status=[];pz=[];geom=[];entry=[]
    for i in selected:
        r,p=native[i],pairs[i];track=r['tracks'][p['leading_index']];state=track['state']
        z=state[5]/1000
        point.append([math.log(z),state[0],state[1],state[3]/state[5],state[4]/state[5]])
        q={v['name']:v for v in p['readout']}
        charge.append([q[name]['raw_charge_pC'] if q[name]['raw_charge_pC'] is not None else float('nan') for name in CHANNELS])
        status.append([q[name]['status'] for name in CHANNELS]);pz.append(z);entry.append(r['entry'])
        g=[]
        for s in r['geometry']['stations'][1:]:
            complete_surface = (s['available'] and s['eligibleWafers'] == s['measuredWafers']
                and s['onMeasuredWafer'] == s['eligibleCandidates'])
            if not complete_surface:g.extend([float('nan'),float('nan')]);continue
            n=s['candidate_N'];total=s['mean_abs_dx_mm']*n if n else 0.
            g.extend([math.asinh(n),math.asinh(total)])
        geom.append(g)
    data=dict(entry=np.asarray(entry,dtype=int),point=clean(point),charge=clean(charge),status=np.asarray(status,dtype=int),
        pz=np.asarray(pz),geometry=np.asarray(geom))
    source=dict(kind='MC_mu100GeV_verified_roots',root_identity='all original4096 matchedStage146 from liveHITS')
    rows,models=evaluate(0,data,dict(MC_truth_mu_only_N=len(selected),selected_muon_N=len(selected),source=source))
    paired_rows=[]
    if all(models[name]['supported'] for name in ['Q15','Q15G6']):
        scored={};alerts={}
        for name in ['Q15','Q15G6']:
            model=models[name]
            y=np.arcsinh(data['charge'])
            if name=='Q15G6':y=np.column_stack([y,data['geometry']])
            available=np.all(np.isfinite(data['point']),axis=1)&np.all(np.isfinite(y),axis=1)
            support=np.all((data['point']>=model['state_lo'])&(data['point']<=model['state_hi']),axis=1)
            scored[name]=(data['entry']%4==3)&available&support
            design=np.column_stack([np.ones(len(entry)),(data['point']-model['state_mean'])/model['state_scale']])
            residual=y-design@np.asarray(model['beta'])
            score=np.einsum('ni,ij,nj->n',residual,np.linalg.inv(model['covariance']),residual)
            alerts[name]=score>model['threshold']
        common=scored['Q15']&scored['Q15G6']
        for group,mask in dict(all=np.ones(len(entry),bool),
                pz50_100=(data['pz']>=50)&(data['pz']<100),
                overflow=np.any((data['status']&4)!=0,axis=1),
                high_activity=data['charge'].sum(axis=1)>models['Q15']['high_activity_train_sum_raw_charge99_pC']).items():
            use=common&mask;a=alerts['Q15'];b=alerts['Q15G6']
            paired_rows.append(dict(group=group,common_scored_N=int(use.sum()),
                both_alert_N=int(np.count_nonzero(use&a&b)),
                only_Q15_alert_N=int(np.count_nonzero(use&a&~b)),
                only_Q15G6_alert_N=int(np.count_nonzero(use&~a&b)),
                neither_alert_N=int(np.count_nonzero(use&~a&~b)),
                Q15_only_support_N=int(np.count_nonzero(mask&scored['Q15']&~scored['Q15G6'])),
                Q15G6_only_support_N=int(np.count_nonzero(mask&scored['Q15G6']&~scored['Q15'])),
                scope='Descriptive fixed-rule paired alerts; no threshold tuning or other-root classification'))
        with (OUT/'paired_alerts.tsv').open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(paired_rows[0]),delimiter='\t',lineterminator='\n')
            writer.writeheader();writer.writerows(paired_rows)
    (OUT/'models.json').write_text(json.dumps(models,indent=2,allow_nan=False)+'\n')
    if rows:
        with (OUT/'heldout.tsv').open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n')
            writer.writeheader();writer.writerows(rows)
    complete=np.all(np.isfinite(data['charge']),axis=1)&np.all(np.isfinite(data['geometry']),axis=1)
    combined=np.column_stack([np.arcsinh(data['charge']),data['geometry']])
    correlation=np.corrcoef(combined[complete],rowvar=False) if complete.sum()>1 else None
    # Keep exact zero-variance/missing correlation undefined rather than repaired.
    corr=[[float(x) if np.isfinite(x) else None for x in row] for row in correlation] if correlation is not None else None
    result=dict(input_parent_N=len(pairs),selected_parent_N=len(selected),unselected_parent_N=len(pairs)-len(selected),
        split_counts={str(k):int(np.count_nonzero(data['entry']%4==k)) for k in range(4)},
        complete_raw15_G6_N=int(complete.sum()),
        high_activity_unknown_raw_parent_N=int(np.count_nonzero(~np.all(np.isfinite(data['charge']),axis=1))),
        heldout_high_activity_unknown_raw_parent_N=int(np.count_nonzero((data['entry']%4==3)&~np.all(np.isfinite(data['charge']),axis=1))),measured_rule_group_rows=len(rows),
        policy_support={name:value['supported'] for name,value in models.items()},response_fit_attempt_N=len(models),
        raw15_G6_correlation=corr,correlation_scope='Descriptive selected complete-parent correlation; not independent information or causal contribution',
        negative_signed_raw_N=int(np.count_nonzero(data['charge']<0)),legal_exact_minus1_raw_N=int(np.count_nonzero(data['charge']==-1)),
        heldout=rows,paired_alerts=paired_rows,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
        RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        population_FPR_certified=False,data_native_calibration='input_missing',energy_fits=0,new_G4=0,reserved_forward=0,
        calibrated_track_covariance=False,other_root_classifier_certified=False)
    (OUT/'response_summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result
