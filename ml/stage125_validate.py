"""Independent row-space checks of inference inputs, weights, risks and intervals."""
import csv
import json
import os
import time
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage125_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage125'
INPUT=Path(os.environ.get('NU_MU_STAGE125_INPUT_ROOT',str(ROOT)))


def load(path):
    with np.load(path) as z:return {k:z[k] for k in z.files}


def main():
    tick=time.perf_counter();d=load(CACHE/'evaluation.npz');old=load(INPUT/'ntuples/energy_ml_stage119/old_input.npz')
    fitted=set(map(tuple,old['incoming'][np.isin(old['role'],[1,2])]))
    assert not any(tuple(k) in fitted for k in d['incoming'][d['primary']])
    unique,inverse=np.unique(d['incoming'],axis=0,return_inverse=True);np.testing.assert_array_equal(inverse,d['key_id'])
    main_rows=list(csv.DictReader((OUT/'metrics.tsv').open(),delimiter='\t'))
    mass=np.random.default_rng(2026110625).poisson(1,(500,len(unique))).astype('float32')
    point_delta=[];CI_delta=[];checks=[]
    for tune in ['FTF_BIC','FTFP_INCLXX','JEFF33','ENDFB8','QGSP_BERT']:
        m=(d['tune']==tune)&d['primary'];ids=inverse[m];prob=d['probability'][m]
        _keys,inv,count=np.unique(d['incoming'][m],axis=0,return_inverse=True,return_counts=True)
        expected=1/(count[inv]*prob);np.testing.assert_allclose(d['weight'][m],expected,rtol=1e-15,atol=0)
        for scope,weight_name in [('primary','weight'),('standardized','standard_weight'),('fully_standardized','matched_weight')]:
            w=d[weight_name][m];used=w>0;ww=mass[:,ids]*w[None,:]
            den=ww.sum(1)
            if scope!='primary':assert abs(w.sum()-1)<1e-12
            for model in ['direct','traditional']:
                row=next(r for r in main_rows if r['scope']==scope and r['tune']==tune and r['model']==model and r['stratum']=='all')
                error=d[model+'_logE'][m]-np.log(d['truth_E_GeV'][m]);values={
                    'log_RMSE':float(np.sqrt(np.average(error**2,weights=w))),
                    'tail50_pct':float(np.average(100*(abs(np.exp(error)-1)>.5),weights=w)),
                    'mean_log_bias':float(np.average(error,weights=w))}
                for key,value in values.items():point_delta.append(abs(value-float(row[key])))
                distributions={
                    'log_RMSE':np.sqrt((ww@(error**2))/den),
                    'tail50_pct':(ww@(100*(abs(np.exp(error)-1)>.5)))/den,
                    'mean_log_bias':(ww@error)/den}
                for key,value in distributions.items():
                    bounds=np.quantile(value,[.025,.975]);target=[float(row[key+'_low95']),float(row[key+'_high95'])]
                    CI_delta.extend(abs(bounds-target))
                checks.append(dict(tune=tune,scope=scope,model=model,checked_point_metrics=3,checked_interval_bounds=6))
    maximum_point=float(max(point_delta));maximum_CI=float(max(CI_delta))
    assert maximum_point<1e-10 and maximum_CI<1e-10,(maximum_point,maximum_CI)
    matrix=list(csv.DictReader((OUT/'matrices.tsv').open(),delimiter='\t'));columns={}
    for r in matrix:
        key=(r['scheme'],r['tune'],r['model'],r['true_bin']);columns.setdefault(key,[]).append(r)
    for rr in columns.values():
        if float(rr[0]['truth_weight'])>0:assert abs(sum(float(r['probability']) for r in rr)-1)<1e-12
    output=dict(passed=True,primary_train_cal_overlap=0,source_input_weights_verified=True,
                row_space_checks=checks,point_max_abs_delta=maximum_point,CI_bound_max_abs_delta=maximum_CI,
                all_truth_columns_normalized=True,wall_s=time.perf_counter()-tick)
    (OUT/'independent_validation.json').write_text(json.dumps(output,indent=2)+'\n');print(output,flush=True)


if __name__=='__main__':main()
