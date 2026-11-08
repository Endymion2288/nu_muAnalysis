"""Independent scalar transforms/metrics plus actual saved-model reloads, batch only."""
import csv
import math

import xgboost as xgb
from stage191_common import *


def check_intervals(d,policies,pairs):
    checks=[]
    for role in [2,3]:
        ix=np.flatnonzero(d['role']==role)
        sd={k:v[ix] for k,v in d.items() if isinstance(v,np.ndarray) and len(v)==len(d['role'])}
        _,first,gid=np.unique(sd['incoming'],axis=0,return_index=True,return_inverse=True)
        rng=np.random.default_rng(20261107129+role);draw=np.zeros((500,len(first)),np.int16)
        for component in sorted(set(sd['component'][first])):
            u=np.flatnonzero(sd['component'][first]==component)
            draw[:,u]=rng.multinomial(len(u),np.full(len(u),1/len(u)),size=500)
        w=energy.weights(sd['incoming'])
        for layer,mask in energy.masks(sd).items():
            if layer not in energy.LAYERS:
                continue
            selected=ix[mask];wt=draw[:,gid[mask]]*w[mask];den=wt.sum(1);good=den>0
            for ref in ['V','S']:
                a=policies['C'][selected]-np.log(d['truth_E_GeV'][selected])
                b=policies[ref][selected]-np.log(d['truth_E_GeV'][selected])
                aa=wt@a**2;bb=wt@b**2;ok=good&(bb>0)
                row=next(q for q in pairs if int(q['role'])==role and q['stratum']==layer and q['candidate']=='C' and q['reference']==ref)
                observed=np.quantile(np.sqrt(aa[ok]/bb[ok]),[.025,.975])
                delta=max(abs(observed[0]-float(row['low95'])),abs(observed[1]-float(row['high95'])))
                for sign,fa,fb in [('total',abs(np.expm1(a))>.5,abs(np.expm1(b))>.5),('positive',np.expm1(a)>.5,np.expm1(b)>.5),('negative',np.expm1(a)<-.5,np.expm1(b)<-.5)]:
                    tails=np.quantile(100*(wt@(fa.astype(float)-fb.astype(float)))[ok]/den[ok],[.025,.975])
                    delta=max(delta,abs(tails[0]-float(row[sign+'_tail_low95_pp'])),abs(tails[1]-float(row[sign+'_tail_high95_pp'])))
                assert delta<1e-9
                checks.append(dict(role=role,stratum=layer,reference=ref,max_difference=delta))
    return checks


def main():
    d,x,names=inputs();active=d['role']>0
    p=json.loads((OUT/'protocol.json').read_text())
    saved=load(CACHE/'control.npz')
    content=saved['content'];perm=saved['permutation']
    np.testing.assert_array_equal(content,x['C'][:,-12:])
    np.testing.assert_array_equal(content[perm],x['S'][:,-12:])
    np.testing.assert_array_equal(np.sort(perm[active]),np.flatnonzero(active))
    np.testing.assert_array_equal(d['role'][perm],d['role'])
    np.testing.assert_array_equal(d['component'][perm],d['component'])
    np.testing.assert_array_equal(saved['availability'][perm],saved['availability'])
    np.testing.assert_array_equal(np.isfinite(content[perm]),np.isfinite(content))
    transform_checks=0;maxdiff=0.;raw_checks=[]
    from stage191_review import read,validate
    for group in range(35):
        data=read(f'full_{group}');raw_checks.append(dict(group=group,**validate(data,d)))
        for r in data['audit_records']:
            m=r['measurement'];row=r['case']['row'];a=saved['availability'][row]
            for layer in range(3):
                if not a[layer+1]:continue
                wafers=[w for w in m['wafers'] if w['layer']==layer and w['success'] and w['inside_geometric_bounds']
                    and w.get('covariance') and w['covariance'][0][0] is not None and w['covariance'][0][0]>0
                    and all(q.get('pull') is not None and math.isfinite(q['pull']) for q in w['candidates'])]
                assert len(wafers)==a[layer+1]
                pulls=np.asarray([q['pull'] for w in wafers for q in w['candidates']],float)
                kernel=np.exp(-.5*pulls**2)
                independent=np.array([np.log1p(len(pulls)),np.log1p(np.count_nonzero(abs(pulls)<=3)),
                    np.log1p(kernel.sum()),np.dot(pulls,kernel)/(1+kernel.sum())],dtype='float32')
                delta=float(np.max(abs(independent-content[row,layer*4:layer*4+4])))
                assert delta<=1e-6;maxdiff=max(maxdiff,delta);transform_checks+=4
    primitive_names=names['X'];qidx=[primitive_names.index(n) for n in p['conditioning_charge_columns']]
    for i in np.flatnonzero(active):
        k=int(perm[i])
        assert sum(d['pz'][i]>=e for e in p['pz_edges_GeV'])==sum(d['pz'][k]>=e for e in p['pz_edges_GeV'])
        qs=[]
        for row in [i,k]:
            raw=list(map(float,d['x'][row,qidx]))
            value=math.asinh(math.fsum(raw)) if all(map(math.isfinite,raw)) else math.inf
            qs.append(sum(value>=e for e in p['activity_edges']))
        assert qs[0]==qs[1]
        for layer in range(3):
            a0,b0=map(float,saved['sigma'][[i,k],layer])
            aa=math.exp(a0) if math.isfinite(a0) else math.inf
            bb=math.exp(b0) if math.isfinite(b0) else math.inf
            assert sum(aa>=e for e in p['sigma_edges_mm'])==sum(bb>=e for e in p['sigma_edges_mm'])
    protocol=json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())['baseline']
    allp={}
    for arm in ['X','A','V','C','S']:
        matrix=xgb.DMatrix(x[arm][active],feature_names=names[arm],nthread=1)
        predictions=[]
        for seed in protocol['seeds']:
            model=xgb.Booster(params={'nthread':1});model.load_model(ART/f'ift_{arm}_{seed}.ubj')
            predictions.append(model.predict(matrix).astype(float))
        raw=np.full(len(active),np.nan);raw[active]=np.mean(predictions,axis=0)
        cache=load(ART/f'ift_{arm}_prediction.npz')
        np.testing.assert_array_equal(raw,cache['raw'])
        cal=d['role']==2
        offset=float(np.average(np.log(d['truth_E_GeV'][cal])-raw[cal],weights=energy.weights(d['incoming'][cal])))
        np.testing.assert_array_equal(raw+offset,cache['cal'])
        assert np.isnan(cache['cal'][~active]).all()
        allp[arm]=cache['cal']
    metrics=list(csv.DictReader((OUT/'ift_metrics.tsv').open(),delimiter='\t'))
    checks=[];deltas=[]
    for role in [2,3]:
        ix=np.flatnonzero(d['role']==role)
        sd={k:v[ix] for k,v in d.items() if isinstance(v,np.ndarray) and len(v)==len(active)}
        w=energy.weights(sd['incoming']);strata=energy.masks(sd)
        for layer in energy.LAYERS:
            mask=strata[layer];selected=ix[mask];wt=w[mask]
            if not len(selected):continue
            den=math.fsum(map(float,wt))
            for arm in allp:
                err=allp[arm][selected]-np.log(d['truth_E_GeV'][selected])
                rmse=math.sqrt(math.fsum(float(a)*float(b)**2 for a,b in zip(wt,err))/den)
                row=next(r for r in metrics if int(r['role'])==role and r['stratum']==layer and r['model']==arm)
                delta=abs(rmse-float(row['log_RMSE']))
                for col,flag in [('tail50_pct',abs(np.expm1(err))>.5),('positive_tail50_pct',np.expm1(err)>.5),('negative_tail50_pct',np.expm1(err)<-.5)]:
                    value=100*math.fsum(float(a)*int(b) for a,b in zip(wt,flag))/den
                    delta=max(delta,abs(value-float(row[col])))
                assert delta<1e-10
                deltas.append(delta);checks.append(dict(role=role,stratum=layer,arm=arm,N=len(selected)))
    pairs=list(csv.DictReader((OUT/'ift_paired.tsv').open(),delimiter='\t'))
    expansion={}
    for ref in ['X','A','V','S']:
        rows=[r for r in pairs if r['candidate']=='C' and r['reference']==ref and int(r['role']) in [2,3] and r['stratum'] in energy.LAYERS[:2]]
        assert len(rows)==4
        low=all(float(r['RMSE_ratio'])<=.95 and float(r['high95'])<1 for r in rows)
        guards=[r for r in pairs if r['candidate']=='C' and r['reference']==ref and int(r['role']) in [2,3] and r['stratum'] in energy.LAYERS]
        tails=all(float(r[s+'_tail_high95_pp'])<=2 for r in guards for s in ['total','positive','negative'])
        expansion[ref]=dict(two_low_cal_test_pass=low,tail_guard_pass=tails,passed=bool(low and tails))
    original_guards=[r for r in pairs if r['candidate']=='C' and r['reference']=='direct_cal' and int(r['role']) in [2,3] and r['stratum'] in energy.LAYERS]
    original_tails=bool(len(original_guards)==16 and all(float(r[s+'_tail_high95_pp'])<=2 for r in original_guards for s in ['total','positive','negative']))
    interval_checks=check_intervals(d,allp,pairs)
    write('content_decision.json',dict(expansion=expansion,original_tail_guards_pass=original_tails,
        expand=bool(original_tails and all(r['passed'] for r in expansion.values())),
        fixed_package_ended=True,no_representation_seed_capacity_scan=True,promotion=False,overall_complete=False))
    write('independent_validation.json',dict(passed=True,actual_models_reloaded_N=15,
        all_active_predictions_exact=True,calibration_exact=True,scalar_transform_checks_N=transform_checks,
        max_scalar_transform_float32_difference=maxdiff,shuffle_original_roles_component_support_exact=True,
        raw_source_audits=raw_checks,independent_row_bootstrap_checks=interval_checks,central_metrics_checks=checks,max_central_metric_difference=max(deltas),
        quarantine_predictions=0,reserved_predictions=0,overall_complete=False))


if __name__=='__main__':main()
