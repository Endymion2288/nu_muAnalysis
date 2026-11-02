#!/usr/bin/env python3
"""Eight frozen convex fits, grouped cal OOF, then one final eval prediction."""
import json
import numpy as np

from expert_combination import (OUT, ART, begin, resources, inputs, route, subset,
                                optimize, predict, save, masks, LOW, COST)

start = begin(); protocol=json.loads((OUT/'protocol.json').read_text())
assert not (OUT/'models.json').exists() and not (ART/'predictions.npz').exists()
d=inputs(); dc=subset(d,d['role']=='cal'); de=subset(d,d['role']=='eval')
boundaries=protocol['timing_medians_pC'];cell=route(dc['pz'],dc['timing'],boundaries)
fold=np.array([protocol['fold_by_group'][str(g)] for g in dc['group']]);models={};arrays={}
for k in ['row']:arrays['cal_'+k]=dc[k];arrays['eval_'+k]=de[k]
arrays['cal_fold']=fold
calls=0
for family in protocol['families']:
    fitted=[];oof=np.full(len(fold),np.nan);oof_f7=np.full(len(fold),np.nan)
    for f in range(3):
        train=fold!=f;hold=~train
        assert not set(dc['group'][train]) & set(dc['group'][hold])
        model=optimize(subset(dc,train),cell[train],family,protocol['numerical_secondary_epsilon']);calls+=1
        model.update(held_fold=f,train_groups=sorted(set(dc['group'][train])),held_groups=sorted(set(dc['group'][hold])))
        oof[hold]=predict(dc['pz'][hold],dc['timing'][hold],dc['raw_F7'][hold],model,boundaries)
        oof_f7[hold]=dc['raw_F7'][hold]+model['offset_log']
        fitted.append(model)
        print(family,'fold',f,'max low-E MSE ratio',model['objective_max_low_MSE_ratio'],'KKT',model['projected_KKT_max_abs'],flush=True)
    final=optimize(dc,cell,family,protocol['numerical_secondary_epsilon']);calls+=1
    models[family]=dict(folds=fitted,final=final)
    assert np.all(np.isfinite(oof))
    arrays['cal_oof_'+family]=oof;arrays['cal_oof_F7']=oof_f7
    arrays['cal_final_'+family]=predict(dc['pz'],dc['timing'],dc['raw_F7'],final,boundaries)
    # Models and routing are now frozen before evaluating final outputs.
    arrays['eval_'+family]=predict(de['pz'],de['timing'],de['raw_F7'],final,boundaries)
    print(family,'final',final,flush=True)
assert calls==protocol['combination_optimization_calls']==8
np.testing.assert_equal(models['two']['final']['offset_log'],models['three']['final']['offset_log'])
arrays['eval_F7']=de['raw_F7']+models['three']['final']['offset_log']
ART.mkdir(parents=True,exist_ok=True);np.savez_compressed(ART/'predictions.npz',**arrays)
save(OUT/'models.json',models)
save(OUT/'optimization_resources.json',dict(**resources(start),combination_optimizer_calls=calls,
     new_energy_model_fits=0,solver_wall_sum_s=sum(m['solver_wall_s'] for f in models.values() for m in f['folds']+[f['final']]),
     retained_prediction_bytes=(ART/'predictions.npz').stat().st_size))
