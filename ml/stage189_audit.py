"""Independent scalar transforms/metrics plus actual saved-model reloads, batch only."""
import csv
import math

import xgboost as xgb
from stage189_common import *


def main():
    d,x,names=inputs();active=d['role']>0
    p=json.loads((OUT/'protocol.json').read_text())
    saved=load(CACHE/'control.npz')
    content=saved['content'];perm=saved['permutation']
    np.testing.assert_array_equal(content,x['C'][:,-4:])
    np.testing.assert_array_equal(content[perm],x['S'][:,-4:])
    np.testing.assert_array_equal(np.sort(perm[active]),np.flatnonzero(active))
    np.testing.assert_array_equal(d['role'][perm],d['role'])
    np.testing.assert_array_equal(d['component'][perm],d['component'])
    np.testing.assert_array_equal(np.isfinite(content[perm]),np.isfinite(content))
    primitive_names=names['X'];maxdiff=0.;transform_checks=0
    for j,pair in enumerate(p['pairs']):
        a,b=[primitive_names.index(n) for n in pair]
        for i in np.flatnonzero(active):
            q1,q2=map(float,d['x'][i,[a,b]])
            if not (math.isfinite(q1) and math.isfinite(q2)):
                assert math.isnan(float(content[i,j]));continue
            scalar=np.float32(math.asinh(q1/p['Q0_pC'])-math.asinh(q2/p['Q0_pC']))
            delta=abs(float(scalar)-float(content[i,j]));maxdiff=max(maxdiff,delta)
            assert delta<=5e-7
            transform_checks+=1
    # Verify observable shuffle conditions independently, including the missing activity bin.
    qidx=[primitive_names.index(n) for n in p['conditioning_charge_columns']]
    for i in np.flatnonzero(active):
        k=int(perm[i])
        assert sum(d['pz'][i]>=e for e in p['pz_condition_edges_GeV'])==sum(d['pz'][k]>=e for e in p['pz_condition_edges_GeV'])
        qs=[]
        for row in [i,k]:
            raw=list(map(float,d['x'][row,qidx]))
            s=math.asinh(math.fsum(raw)/p['Q0_pC']) if all(map(math.isfinite,raw)) else math.inf
            qs.append(sum(s>=e for e in p['asinh_charge_condition_edges']))
        assert qs[0]==qs[1]
    protocol=json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())['baseline']
    allp={}
    for arm in ['X','A','C','S']:
        matrix=xgb.DMatrix(x[arm][active],feature_names=names[arm],nthread=1)
        predictions=[]
        for seed in protocol['seeds']:
            model=xgb.Booster(params={'nthread':1});model.load_model(ART/f'composition_{arm}_{seed}.ubj')
            predictions.append(model.predict(matrix).astype(float))
        raw=np.full(len(active),np.nan);raw[active]=np.mean(predictions,axis=0)
        cache=load(ART/f'composition_{arm}_prediction.npz')
        np.testing.assert_array_equal(raw,cache['raw'])
        cal=d['role']==2
        offset=float(np.average(np.log(d['truth_E_GeV'][cal])-raw[cal],weights=energy.weights(d['incoming'][cal])))
        np.testing.assert_array_equal(raw+offset,cache['cal'])
        assert np.isnan(cache['cal'][~active]).all()
        allp[arm]=cache['cal']
    metrics=list(csv.DictReader((OUT/'composition_metrics.tsv').open(),delimiter='\t'))
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
    pairs=list(csv.DictReader((OUT/'composition_paired.tsv').open(),delimiter='\t'))
    expansion={}
    for ref in ['X','A','S']:
        rows=[r for r in pairs if r['candidate']=='C' and r['reference']==ref and int(r['role']) in [2,3] and r['stratum'] in energy.LAYERS[:2]]
        assert len(rows)==4
        low=all(float(r['RMSE_ratio'])<=.95 and float(r['high95'])<1 for r in rows)
        guards=[r for r in pairs if r['candidate']=='C' and r['reference']==ref and int(r['role']) in [2,3] and r['stratum'] in energy.LAYERS]
        tails=all(float(r[s+'_tail_high95_pp'])<=2 for r in guards for s in ['total','positive','negative'])
        expansion[ref]=dict(two_low_cal_test_pass=low,tail_guard_pass=tails,passed=bool(low and tails))
    write('content_decision.json',dict(expansion=expansion,expand=all(r['passed'] for r in expansion.values()),
        fixed_package_ended=True,no_transform_seed_capacity_scan=True,promotion=False,overall_complete=False))
    write('independent_validation.json',dict(passed=True,actual_models_reloaded_N=12,
        all_active_predictions_exact=True,calibration_exact=True,scalar_transform_checks_N=transform_checks,
        max_scalar_transform_float32_difference=maxdiff,shuffle_original_roles_component_support_exact=True,
        central_metrics_checks=checks,max_central_metric_difference=max(deltas),
        quarantine_predictions=0,reserved_predictions=0,overall_complete=False))


if __name__=='__main__':main()
