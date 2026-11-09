"""Independent leakage, weight, scalar-metric and saved-model checks on all rows."""
import csv
import json
import math
import time
from collections import defaultdict

import numpy as np
import xgboost as xgb

from audited_features import configuration,clean
from stage199_common import DATA_ROOT,OUT,load,save,resources


def precise_leaf_sum(model,matrix):
    """Re-sum native float32 leaf weights in float64 along CPU leaf paths."""
    config=json.loads(model.save_config())['learner']['learner_model_param']
    base=json.loads(config['base_score'])
    if isinstance(base,list):base=base[0]
    base=float(np.float32(float(base)))
    leaves=model.predict(matrix,pred_leaf=True).astype(np.int32).T.copy()
    total=np.full(matrix.num_row(),base,dtype=np.float64)
    absolute=np.full(matrix.num_row(),abs(base),dtype=np.float64)
    trees=model.get_dump(dump_format='json')
    assert leaves.shape==(len(trees),matrix.num_row())
    for ids,tree in zip(leaves,trees):
        nodes=[json.loads(tree)];values={}
        while nodes:
            node=nodes.pop()
            if 'leaf' in node:values[node['nodeid']]=float(np.float32(node['leaf']))
            else:nodes.extend(node['children'])
        lookup=np.full(max(values)+1,np.nan)
        for key,value in values.items():lookup[key]=value
        v=lookup[ids];assert np.isfinite(v).all()
        total+=v;absolute+=abs(v)
    # Standard forward-error bound for correctly rounded float32 additions,
    # covering all tree terms, the intercept and final float32 rounding.
    operations=len(trees)+2;unit=np.finfo(np.float32).eps/2
    bound=operations*unit/(1-operations*unit)*absolute
    return total,bound


def main():
    tick,cpu=time.perf_counter(),time.process_time()
    d=load(DATA_ROOT/'ntuples/energy_ml_stage199/input.npz')
    z=load(DATA_ROOT/'ntuples/energy_ml_stage199/predictions.npz')
    cfg=configuration();p=json.loads((OUT/'protocol.json').read_text())
    # Rebuild exact incoming/family role sets without using prepare's union IDs.
    role_by_key=defaultdict(set);role_by_event=defaultdict(set);role_by_evnt=defaultdict(set)
    count_by_key=defaultdict(int);raw64=defaultdict(set)
    for i in range(len(d['role'])):
        key=tuple(float(np.float32(v)) for v in d['incoming'][i]);r=int(d['role'][i]);event=int(d['eventID'][i])
        role_by_key[key].add(r);count_by_key[key]+=1
        canonical=str(d['flux'][i]).removeprefix('24_xing_angle_wo_caloNu_')
        assert canonical==str(d['canonical_flux'][i])
        role_by_event[(canonical,event)].add(r)
        role_by_evnt[(str(d['EVNT'][i]),event)].add(r)
    assert all(len(v)==1 for v in role_by_key.values())
    assert all(len(v)==1 for v in role_by_event.values())
    assert all(len(v)==1 for v in role_by_evnt.values())
    assert set(d['role'])=={1,2,3}
    b=np.array([max(j for j,e in enumerate(p['weights']['edges_GeV']) if value>=e) for value in d['truth_E_GeV']])
    np.testing.assert_array_equal(b,d['energy_bin'])
    expected=np.array([1/count_by_key[tuple(float(np.float32(v)) for v in key)] for key in d['incoming']])
    np.testing.assert_array_equal(expected,d['weight'])
    mass=[math.fsum(float(w) for w in expected[(d['role']==1)&(b==j)]) for j in range(8)]
    total=math.fsum(mass);nonempty=sum(v>0 for v in mass)
    factors=[total/(nonempty*v) if v else 0 for v in mass]
    flat=np.array([w*factors[j] for w,j in zip(expected,b)])
    np.testing.assert_allclose(flat,d['flat_weight'],rtol=2e-12,atol=1e-12)
    # Primitive domain/sentinel checks use policy rules, independently of joins.
    for j,name in enumerate(cfg['features']):
        np.testing.assert_array_equal(d['x'][:,j],clean(d['x'][:,j],cfg['rules'][name]).astype('float32'))
    assert not set(cfg['features'])&{'ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0'}
    for key in ['run','eventID','role']:np.testing.assert_array_equal(z[key],d[key])
    sourceids=set(map(int,d['source']))
    assert sourceids=={s['index'] for s in p['sources']}
    assert set(map(int,d['run']))==set(range(200080,200102))
    assert len(set(zip(map(int,d['run']),map(int,d['eventID']))))==len(d['role'])
    # This exact roundtrip permits deleting only newly generated duplicate shards.
    prior=load(DATA_ROOT/'ntuples/energy_ml_stage130/new_input.npz');roundtrip=0
    for s in p['sources']:
        take=d['source']==s['index']
        if s['mode']=='cache130':
            old=prior['source']==s['index']
            for key in ['x','incoming','run','eventID','truth_E_GeV','y_lepton','primary_valid','confirmed','raw_charge','status','calo_status','pz']:
                np.testing.assert_array_equal(d[key][take],prior[key][old]);roundtrip+=1
        else:
            phase='pilot' if s['mode']=='local' and s['index'] in p['pilot_indices'] else 'production'
            shard=load(DATA_ROOT/f"ntuples/energy_ml_stage199/{phase}_{s['index']}/selected.npz")
            for key in ['x','incoming','run','eventID','truth_E_GeV','y_lepton','primary_valid','confirmed','raw_charge','status','calo_status']:
                np.testing.assert_array_equal(d[key][take],shard[key]);roundtrip+=1
            np.testing.assert_array_equal(d['pz'][take],shard['reco_pz_GeV']);roundtrip+=1
    # All six models, all predictions, float32 native tree traversal on CPU.
    matrix=xgb.DMatrix(d['x'],feature_names=cfg['features'],nthread=8)
    model_checks=[];fit=json.loads((OUT/'fit.json').read_text());y=np.log(d['truth_E_GeV'])
    for arm in ['incoming','flat']:
        preds=[];precise=[];bounds=[];seed_checks=[]
        for seed in p['model']['seeds']:
            model=xgb.Booster(params={'device':'cpu','nthread':8})
            model.load_model(DATA_ROOT/f'ml/artifacts/stage199/{arm}_{seed}.ubj')
            assert model.num_boosted_rounds()==400 and model.feature_names==cfg['features']
            predicted=model.predict(matrix).astype(float)
            accurate,bound=precise_leaf_sum(model,matrix)
            cpu_error=abs(predicted-accurate)
            assert np.all(cpu_error<=bound+1e-10)
            preds.append(predicted);precise.append(accurate);bounds.append(bound)
            seed_checks.append(dict(seed=seed,CPU_float64_leaf_sum_max_abs_difference=float(cpu_error.max()),
                max_float32_forward_error_bound=float(bound.max()),all_rows_within_forward_error_bound=True))
        mean=np.mean(preds,axis=0);difference=float(np.max(abs(mean-z[arm+'_raw'])))
        accurate=np.mean(precise,axis=0);bound=np.mean(bounds,axis=0)
        gpu_error=abs(accurate-z[arm+'_raw'])
        assert np.all(gpu_error<=bound+1e-10)
        assert np.all(abs(mean-z[arm+'_raw'])<=2*bound+1e-10)
        cal=d['role']==2
        for name,w in [('cal',expected),('flatcal',flat)]:
            off=math.fsum(float(a*b) for a,b in zip((y-z[arm+'_raw'])[cal],w[cal]))/math.fsum(map(float,w[cal]))
            assert abs(off-fit['offsets'][arm][name])<2e-12
            np.testing.assert_allclose(z[arm+'_raw']+off,z[arm+'_'+name],rtol=0,atol=2e-12)
        model_checks.append(dict(arm=arm,models_N=3,all_rows_N=len(mean),CPU_GPU_max_abs_log_prediction_difference=difference,
            GPU_float64_leaf_sum_max_abs_log_difference=float(gpu_error.max()),
            max_ensemble_float32_forward_error_bound=float(bound.max()),all_rows_within_float32_forward_error_bound=True,
            seed_checks=seed_checks))
    # Independent scalar central risks and three tails for the complete reported strata.
    with (OUT/'metrics.tsv').open() as f:rows=list(csv.DictReader(f,delimiter='\t'))
    scalar_checks=0;maximum=0.
    def mask(name):
        e,pp,yy=d['truth_E_GeV'],d['pz'],d['y_lepton']
        if name=='all':return np.ones(len(e),bool)
        if name=='E200_inf':return e>=200
        if name.startswith('E'):
            lo,hi=name[1:].split('_');return (e>=float(lo))&((e<float(hi)) if hi!='inf' else True)
        if name=='pz50_100':return (pp>=50)&(pp<100)
        if name=='pz50_100_trueE200':return (pp<100)&(e>=200)
        if name=='high_y':return d['primary_valid']&np.isfinite(yy)&(yy>=.8)&(yy<1)
        if name=='unconfirmed':return ~d['confirmed']
        if name in ['input_missing','fit_failure','negative_valid_raw']:return d[name]
        return None
    for row in rows:
        m=mask(row['stratum'])
        if m is None:continue
        ix=np.flatnonzero(m&(d['role']==int(row['role'])))
        if not len(ix):continue
        w=expected[ix] if row['spectrum']=='original' else flat[ix]
        pred=np.log(d['pz'][ix]/.8) if row['model']=='traditional' else z[row['model']][ix]
        error=pred-y[ix];rel=[math.expm1(float(v)) for v in error];den=math.fsum(map(float,w))
        values=dict(log_RMSE=math.sqrt(math.fsum(float(a*b*b) for a,b in zip(w,error))/den),
            mean_bias_pct=100*math.fsum(float(a*b) for a,b in zip(w,rel))/den)
        for name,fun in [('tail50_pct',lambda x:abs(x)>.5),('positive_tail50_pct',lambda x:x>.5),('negative_tail50_pct',lambda x:x<-.5)]:
            values[name]=100*math.fsum(float(a) for a,b in zip(w,rel) if fun(b))/den
        for key,value in values.items():
            difference=abs(value-float(row[key]));maximum=max(maximum,difference)
            assert difference<2e-9,(row,key,value)
            scalar_checks+=1
    with (OUT/'paired.tsv').open() as f:paired=list(csv.DictReader(f,delimiter='\t'))
    interval_checks=0
    for r in [2,3]:
        ids=np.flatnonzero(d['role']==r)
        families,first,gid=np.unique(d['family'][ids],return_index=True,return_inverse=True)
        components=d['component'][ids[first]];rng=np.random.default_rng(20261109200+r)
        draws=np.zeros((500,len(families)),np.int16)
        for component in np.unique(components):
            pos=np.flatnonzero(components==component)
            draws[:,pos]=rng.multinomial(len(pos),np.full(len(pos),1/len(pos)),size=500)
        for name in ['E50_100','E100_200']:
            take=mask(name)[ids];ix=ids[take]
            # Row-space calculation, independent of report's family-binned sums.
            ww=draws[:,gid[take]]*d['weight'][ix]
            den=ww.sum(1);a=z['flat_cal'][ix]-y[ix];b=z['incoming_cal'][ix]-y[ix]
            ratio=np.sqrt(np.sum(ww*(a*a),axis=1)/np.sum(ww*(b*b),axis=1))
            row,=[v for v in paired if v['role']==str(r) and v['spectrum']=='original' and v['stratum']==name
                   and v['candidate']=='flat_cal' and v['reference']=='incoming_cal']
            np.testing.assert_allclose(np.quantile(ratio,[.025,.975]),[float(row['low95']),float(row['high95'])],rtol=0,atol=2e-10)
            interval_checks+=2
            for tail,fun in [('total',lambda v:abs(np.expm1(v))>.5),('positive',lambda v:np.expm1(v)>.5),('negative',lambda v:np.expm1(v)<-.5)]:
                delta=100*np.sum(ww*(fun(a).astype(float)-fun(b)),axis=1)/den
                np.testing.assert_allclose(np.quantile(delta,[.025,.975]),[float(row[tail+'_tail_low95_pp']),float(row[tail+'_tail_high95_pp'])],rtol=0,atol=2e-10)
                interval_checks+=2
    snapshot=json.loads((OUT.parent/'stage158_energy_ml/preexisting_asset_snapshot.json').read_text())
    for path,expectedstat in snapshot.items():
        st=(DATA_ROOT/path).stat();assert st.st_size==expectedstat['bytes'] and st.st_mtime_ns==expectedstat['mtime_ns']
    save('independent_validation.json',dict(passed=True,records_N=len(d['role']),sources_N=len(sourceids),
        incoming_role_sets_N=len(role_by_key),canonical_flux_event_role_sets_N=len(role_by_event),EVNT_event_role_sets_N=len(role_by_evnt),
        all_parent_and_incoming_role_sets_single=True,all_sources_included=True,old_quarantine_reserved_policy_overridden_as_requested=True,
        base_weights_exact=True,flat_weights_train_only=True,model_checks=model_checks,
        CPU_xgboost_version=xgb.__version__,GPU_fitted_xgboost_version=json.loads((OUT/'platform.json').read_text())['xgboost'],
        numerical_validation='All six CPU leaf-path sums accumulated in float64 on every row; frozen GPU ensemble and CPU replay within row-specific float32 forward-error bounds. Calibration independently recomputed from actual frozen predictions at 2e-12, no energy refit or changed physics gates.',
        source_array_roundtrip_checks_N=roundtrip,
        scalar_risk_tail_checks_N=scalar_checks,max_scalar_difference=maximum,
        independent_rowspace_low_bin_interval_endpoints_N=interval_checks,
        Stage54_assets_preserved_N=len(snapshot),source_system_independence_unmeasured=True,**resources(tick,cpu)))
    print('Independent full-data split/weights/model/scalar checks passed',flush=True)


if __name__=='__main__':main()
