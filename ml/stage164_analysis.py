"""Six locked cached-oracle fits, preserving the existing A/H references."""
import json
import multiprocessing as mp
import resource
import time
import numpy as np
import xgboost as xgb
from audited_features import configuration
from stage164_common import ROOT,OUT,CACHE,ART,load,inputs,protocol,table

G=None


def one(spec):
    arm,seed=spec;d,p,matrices,names=G;cpu,tick=time.process_time(),time.perf_counter();train=d['role']==1
    x=matrices[arm];y=np.log(d['truth_E_GeV'][train]);w=d['weight'][train];w=w/w.mean()
    pars=dict(p['xgboost'],seed=seed,base_score=float(np.average(y,weights=w)),boost_from_average=0)
    model=xgb.train(pars,xgb.DMatrix(x[train],label=y,weight=w,feature_names=names[arm],nthread=1),num_boost_round=p['rounds'])
    model.save_model(ART/f'{arm}_{seed}.ubj');dm=xgb.DMatrix(x,feature_names=names[arm],nthread=1);pred=model.predict(dm).astype(float)
    again=xgb.Booster(params={'nthread':1});again.load_model(ART/f'{arm}_{seed}.ubj');np.testing.assert_array_equal(pred,again.predict(dm))
    return dict(arm=arm,seed=seed,reload_exact=True,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
                RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),pred


def main():
    global G
    assert json.loads((OUT/'qa_summary.json').read_text())['passed']
    assert not (OUT/'fit_lock.json').exists() and not ART.exists(),'No fit retries to optimize heldout risk'
    cpu,tick=time.process_time(),time.perf_counter();d=inputs();matrices=load(CACHE/'fit_matrix.npz')
    base=json.loads((ROOT/'workbook/stage137_energy_ml/protocol.json').read_text())['baseline']
    anames=configuration()['features']+[f'oracle_available_{i}' for i in range(7)]
    names=dict(AZ=anames+['truth_vertex_z_mm'],AZH=anames+['truth_vertex_z_mm','H_KE'])
    (OUT/'fit_lock.json').write_text(json.dumps(dict(arms=['AZ','AZH'],fits=6))+'\n');ART.mkdir(parents=True)
    G=d,base,matrices,names
    with mp.get_context('fork').Pool(4) as pool:results=pool.map(one,[(a,s) for a in ['AZ','AZH'] for s in base['seeds']])
    pred=load('ml/artifacts/stage137/energy_predictions.npz');offsets={};raws={};cal=d['role']==2
    for arm in ['AZ','AZH']:
        raw=np.mean([v for r,v in results if r['arm']==arm],axis=0);raws[arm]=raw
        offsets[arm]=float(np.average(np.log(d['truth_E_GeV'][cal])-raw[cal],weights=d['weight'][cal]));pred[arm]=raw+offsets[arm]
    np.savez_compressed(ART/'energy_predictions.npz',**pred);np.savez_compressed(ART/'raw_predictions.npz',**raws)
    (OUT/'fits.json').write_text(json.dumps(dict(results=[r for r,_ in results],offsets=offsets,energy_fits=6,reference_retrained=False),indent=2)+'\n')
    # Reuse the original scientific definitions and draws, changing only output routing
    # and the two predeclared arms/contrasts, never the frozen masks or risk policy.
    import stage137_evaluate as evaluation
    evaluation.OUT=OUT;evaluation.CACHE=CACHE;evaluation.ART=ART;evaluation.table=table
    evaluation.protocol=lambda:dict(arms=['AZ','AZH'],comparisons=protocol()['comparisons']+[['H','A']])
    evaluation.main()
    import csv
    from stage119_curve_common import LAYERS
    paired=list(csv.DictReader((OUT/'paired.tsv').open(),delimiter='\t'))
    rows=[r for r in paired if r['candidate']=='AZH' and r['reference']=='AZ' and r['stratum'] in LAYERS]
    low=[r for r in rows if r['stratum'] in LAYERS[:2]]
    point_gate=len(low)==4 and all(float(r['RMSE_ratio'])<=.95 and float(r['high95'])<1 for r in low)
    tails=len(rows)==16 and all(r[s+'_tail_high95_pp']!='NA' and float(r[s+'_tail_high95_pp'])<=2 for r in rows for s in ['total','positive','negative'])
    result=dict(passed=True,conditional_H_four_low_5pct=point_gate,conditional_H_protected_tails=tails,
        conditional_H_continuation=point_gate and tails,promotion=False,overall_complete=False,
        scope='Truth mechanism and finite-policy conditional redundancy, not causal decomposition or deployable measurement',
        parent_CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick)
    (OUT/'mechanism_summary.json').write_text(json.dumps(result,indent=2)+'\n');print(result)


if __name__=='__main__':main()
