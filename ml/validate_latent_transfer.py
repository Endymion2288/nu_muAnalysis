"""Independent arithmetic and source-bootstrap checks for stage86 cached output."""
import csv
import json

import numpy as np

from audited_features import REPO
from support_augmentation import arrays, save, begin, resources

OUT=REPO/'workbook/stage86_energy_ml'


def mask_for(a, name):
    n=len(a['pz']); result=np.ones(n,bool)
    for token in name.split('__'):
        e,p,f=a['truth_E_GeV'],a['pz'],a['y_lepton']; ok=a['label_physical']
        if token=='all': m=np.ones(n,bool)
        elif token.startswith('E'):
            lo,hi=token[1:].split('_');m=e>=float(lo)
            if hi!='inf':m&=e<float(hi)
        elif token.startswith('pz'):
            lo,hi=token[2:].split('_');m=p>=float(lo)
            if hi!='inf':m&=p<float(hi)
        elif token in ['f0_01','f01_05','f05_08','f08_1']:
            lo,hi={'f0_01':(0,.1),'f01_05':(.1,.5),'f05_08':(.5,.8),'f08_1':(.8,1)}[token]
            m=ok&(f>=lo)&(f<hi)
        elif token=='label_unknown':m=~ok
        elif token=='high_y':m=ok&(f>=.8)
        elif token=='confirmed_low_transfer':m=a['confirmed']&ok&(f<.2)
        elif token=='unconfirmed':m=~a['confirmed']
        elif token=='response_nominal':m=~(a['wave_invalid']|a['fit_failure']|a['calo_invalid']|a['input_missing'])
        else:m=a[token]
        result &= m
    return result


def validate():
    start=begin(); d=arrays(OUT/'diagnostics.npz'); b=arrays(OUT/'bootstrap.npz')
    counts=list(csv.DictReader((OUT/'state_counts.tsv').open(),delimiter='\t'))
    risks=list(csv.DictReader((OUT/'risk_intervals.tsv').open(),delimiter='\t'))
    lookup={}
    for row in risks:lookup.setdefault((row['role'],row['stratum'],row['policy']),[]).append(row)
    maxdiff=0.; checked=0; median_draw_checks=0
    original=arrays(REPO/'ntuples/energy_ml_stage55/dataset.npz')
    for role in ['train','cal','eval','new_support','pooled_train']:
        a={k[len(role)+1:]:v for k,v in d.items() if k.startswith(role+'_')}
        groups=b[role+'_groups']; w=b[role+'_weights']; gid=np.searchsorted(groups,a['group'])
        # Reproduce actual component-stratified draws without the production helper.
        rng=np.random.default_rng(2026110386); expected=np.zeros_like(w)
        for component in ['pi','k','charm']:
            ix=np.array([j for j,g in enumerate(groups) if g.startswith(component+':')],int)
            if len(ix):expected[:,ix]=rng.multinomial(len(ix),np.ones(len(ix))/len(ix),size=500)
        np.testing.assert_array_equal(w,expected)
        if role in ['train','cal','eval']:
            for key in ['truth_E_GeV','incoming','y_lepton','primary_valid','primary_candidates','primary_p_GeV','group','confirmed']:
                np.testing.assert_array_equal(a[key],original[key][a['row']])
        mu=(1-a['y_lepton'])*a['truth_E_GeV']; np.testing.assert_array_equal(mu,a['mu_truth_GeV'])
        physical=a['primary_valid']&(a['primary_candidates']==1)&np.isfinite(mu)&(mu>0)&np.isfinite(a['truth_E_GeV'])&(a['truth_E_GeV']>0)&(a['y_lepton']>=0)&(a['y_lepton']<1)
        np.testing.assert_array_equal(physical,a['label_physical'])
        for c in [v for v in counts if v['role']==role]:
            m=mask_for(a,c['stratum']); n=int(m.sum())
            assert n==int(c['N']) and len(np.unique(a['group'][m]))==int(c['groups'])
            assert int((m&physical).sum())==int(c['valid_transfer_N'])
            if not n:continue
            gi=gid[m]; den=np.bincount(gi,minlength=len(groups))@w.T; good=den>0
            for policy in ['traditional','F7','stage84']:
                key=(role,c['stratum'],policy)
                if key not in lookup:continue
                # Independent group aggregation for means and tails, exact multiset medians.
                z=a[policy][m]-np.log(a['truth_E_GeV'][m]); r=np.exp(z)-1
                obs=np.column_stack([z*z,r>.5,r<-.5,(r>.5)|(r<-.5)])
                sums=np.vstack([np.bincount(gi,weights=obs[:,j],minlength=len(groups)) for j in range(4)])
                boot=np.full((500,5),np.nan); vals=(w[good]@sums.T)/den[good,None]
                boot[good,0]=np.sqrt(vals[:,0]);boot[good,2:]=vals[:,1:]*100
                order=np.argsort(r,kind='stable'); gg=gi[order]; rr=r[order]
                for j in np.flatnonzero(good):
                    cumulative=np.cumsum(w[j,gg]); total=int(den[j])
                    boot[j,1]=50*(rr[np.searchsorted(cumulative,(total-1)//2+1)]+rr[np.searchsorted(cumulative,total//2+1)])
                point=[np.sqrt(np.mean(z*z)),100*np.median(r),100*np.mean(r>.5),100*np.mean(r<-.5),100*np.mean((r>.5)|(r<-.5))]
                names=['log_RMSE','median_bias_pct','positive_tail50_pct','negative_tail50_pct','tail50_pct']
                for j,name in enumerate(names):
                    row=next(v for v in lookup[key] if v['metric']==name); ci=np.percentile(boot[good,j],[2.5,97.5])
                    err=max(abs(point[j]-float(row['value'])),abs(ci[0]-float(row['lo95'])),abs(ci[1]-float(row['hi95'])))
                    assert err<1e-10,(key,name,err)
                    assert good.sum()==int(row['valid_draws']);maxdiff=max(maxdiff,float(err));checked+=1
                # Direct event expansion checks the convention independently of both CDF implementations.
                for j in [0,125,499]:
                    if not good[j]:continue
                    expanded=np.repeat(r,w[j,gi]); assert abs(100*np.median(expanded)-boot[j,1])<1e-10
                    median_draw_checks+=1
    save(OUT/'independent_validation.json',dict(passed=True,metric_interval_rows_checked=checked,
        actual_event_expansion_median_checks=median_draw_checks,all_source_draws_per_role=500,
        max_absolute_numeric_difference=maxdiff,original_truth_incoming_identity_joins_exact=True,
        counts_recomputed=True,physical_label_masks_recomputed=True,new_fits=0,new_ROOT_reads=0,new_inference=0,**resources(start)))
    print(f'independent validation passed: {checked} metric/CI rows',flush=True)


if __name__=='__main__':validate()
