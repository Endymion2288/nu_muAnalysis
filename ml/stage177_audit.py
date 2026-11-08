"""Actual model reload and independently computed central physics metrics."""
import csv,math
import xgboost as xgb
from stage177_common import *
if __name__=='__main__':
    from stage177_controls_audit import check
    check()
    d,x,names=inputs();active=d['role']>0;protocol=json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())['baseline'];checks=[];allp={}
    for arm in ['X','V','T']:
        data=xgb.DMatrix(x[arm][active],feature_names=names[arm],nthread=1);pred=[]
        for seed in protocol['seeds']:
            b=xgb.Booster(params={'nthread':1});b.load_model(ART/f'slab_{arm}_{seed}.ubj');pred.append(b.predict(data).astype(float))
        raw=np.full(len(active),np.nan);raw[active]=np.mean(pred,axis=0);saved=load(ART/f'slab_{arm}_prediction.npz');np.testing.assert_array_equal(raw,saved['raw'])
        ix=d['role']==2;w=energy.weights(d['incoming'][ix]);offset=float(np.average(np.log(d['truth_E_GeV'][ix])-raw[ix],weights=w))
        np.testing.assert_array_equal(raw+offset,saved['cal']);assert np.isnan(saved['cal'][~active]).all();allp[arm]=saved['cal']
    table=list(csv.DictReader((OUT/'slab_metrics.tsv').open(),delimiter='\t'));errors=[]
    for role in [2,3]:
        ix=np.flatnonzero(d['role']==role);sd={k:v[ix] for k,v in d.items() if isinstance(v,np.ndarray) and len(v)==len(active)};weights=energy.weights(sd['incoming']);masks=energy.masks(sd)
        for layer in energy.LAYERS:
            mask=masks[layer];selected=ix[mask];w=weights[mask];den=math.fsum(float(v) for v in w)
            if not len(selected):continue
            for arm in ['X','V','T']:
                residual=allp[arm][selected]-np.log(d['truth_E_GeV'][selected]);rmse=math.sqrt(math.fsum(float(a)*float(b)**2 for a,b in zip(w,residual))/den)
                row=next(r for r in table if r['role']==str(role) and r['stratum']==layer and r['model']==arm);delta=abs(rmse-float(row['log_RMSE']))
                for name,flags in [('tail50_pct',abs(np.expm1(residual))>.5),('positive_tail50_pct',np.expm1(residual)>.5),('negative_tail50_pct',np.expm1(residual)<-.5)]:
                    value=100*math.fsum(float(a)*int(b) for a,b in zip(w,flags))/den;delta=max(delta,abs(value-float(row[name])))
                assert delta<1e-10;errors.append(delta);checks.append(dict(role=role,stratum=layer,arm=arm,N=len(selected),scalar_central_metrics_exact=True))
    write('independent_validation.json',dict(passed=True,reloaded_actual_models=9,all_active_ensemble_predictions_exact=True,calibration_offsets_exact=True,scalar_checks=checks,max_scalar_difference=max(errors,default=0),quarantine_predictions=0,reserved_predictions=0,overall_complete=False))
