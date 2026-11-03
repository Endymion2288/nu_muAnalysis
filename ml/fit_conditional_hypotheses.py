#!/usr/bin/env python3
"""Two fixed balanced-BCE discriminators per frozen source split, eight fits total."""
import argparse
import json
import time
import numpy as np
import xgboost as xgb
from group_risk import training_split
from conditional_hypotheses import *


class Budget(xgb.callback.TrainingCallback):
    def __init__(self,start):self.start=start
    def after_iteration(self,model,epoch,evals_log):
        if time.process_time()-self.start[1]>850 or time.perf_counter()-self.start[0]>1700:
            raise RuntimeError('stage74 frozen budget; no retry or shortened scientific candidate')
        return False


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--job',choices=JOBS,required=True)
    parser.add_argument('--check-only',action='store_true');args=parser.parse_args();job=args.job
    start=begin();p=json.loads((OUT/'protocol.json').read_text());assert xgb.__version__==p['xgboost_version']
    d=arrays(CACHE/'input.npz');tr,held,purge=training_split(d,p,job)
    count,mass=proposal(d['pz'][tr],d['truth_E_GeV'][tr]);j=JOBS.index(job)
    train_neg=draw(d['pz'][tr],mass,np.random.default_rng(p['seed']+j))
    roles={'held':held} if held is not None else {r:d['role']==r for r in ['train','cal','eval']}
    eval_rng=np.random.default_rng(p['seed']+j+100)
    negatives={r:train_neg if r=='train' else draw(d['pz'][m],mass,eval_rng) for r,m in roles.items()}
    # Worker precreates the report directory for /usr/bin/time output.
    report=OUT/job;report.mkdir(parents=True,exist_ok=True)
    dest=ART/job;assert not dest.exists();dest.mkdir(parents=True)
    output=dict(proposal_counts=count,proposal_mass=mass)
    for r,m in roles.items():
        output.update({r+'_row':d['row'][m],r+'_negative_log_E':negatives[r],
            r+'_true_q_density':proposal_density(d['pz'][m],np.log(d['truth_E_GeV'][m]),mass)})
    if args.check_only:
        for arm in ARMS:
            names=([p['features'][0]] if arm=='M' else p['features'])+[QUERY]
            xx,label=paired_matrix(d['x'][tr][:4],np.log(d['truth_E_GeV'][tr][:4]),train_neg[:4],arm)
            dm=xgb.DMatrix(xx,label=label,feature_names=names,nthread=1)
            assert dm.num_row()==8 and dm.num_col()==(2 if arm=='M' else 63) and dm.get_weight().size==0
        print(json.dumps(dict(job=job,train_N=int(tr.sum()),formal_fits=0,worker_precreated_directory=True,**resources(start))))
        return
    (dest/'started.txt').write_text('two fixed models; no restart after formal start\n')
    records=[]
    for arm in ARMS:
        fitstart=begin();names=([p['features'][0]] if arm=='M' else p['features'])+[QUERY]
        xx,label=paired_matrix(d['x'][tr],np.log(d['truth_E_GeV'][tr]),train_neg,arm)
        dm=xgb.DMatrix(xx,label=label,feature_names=names,nthread=1);assert dm.get_weight().size==0
        model=xgb.train(dict(p['xgboost'],seed=p['seed']),dm,num_boost_round=400,callbacks=[Budget(start)])
        model.set_attr(reco_inputs=json.dumps(names[:-1]),query_input=QUERY,stage74_protocol=json.dumps(p),arm=arm)
        path=dest/(arm+'.ubj');model.save_model(path)
        restored=xgb.Booster(params={'nthread':1});restored.load_model(path)
        assert model.num_boosted_rounds()==400
        train_logits=model.predict(dm,output_margin=True).reshape(-1,2).astype(float)
        for r,m in roles.items():
            rx,_=paired_matrix(d['x'][m],np.log(d['truth_E_GeV'][m]),negatives[r],arm)
            matrix=xgb.DMatrix(rx,feature_names=names,nthread=1)
            value=model.predict(matrix,output_margin=True)
            np.testing.assert_array_equal(value,restored.predict(matrix,output_margin=True))
            output[r+'_'+arm+'_logits']=value.reshape(-1,2).astype(float)
        values=losses(train_logits);rec=dict(arm=arm,trees=400,reco_features=len(names)-1,query_features=1,
            train_N=int(tr.sum()),pair_rows=2*int(tr.sum()),purged_N=int(purge.sum()),
            train_groups=len(np.unique(d['group'][tr])),train_unique_incoming=len(np.unique(d['incoming'][tr],axis=0)),
            train_scores={k:float(values[k].mean()) for k in ['BCE','positive_BCE','negative_BCE','Brier']},
            model_reload_exact=True,implicit_unit_weights=True,**resources(fitstart))
        records.append(rec);print(json.dumps(rec),flush=True)
        del dm,xx,model,restored
    np.savez_compressed(dest/'predictions.npz',**output);(dest/'started.txt').unlink()
    save(report/'fit.json',dict(job=job,formal_fits=2,proposal_seed=p['seed']+j,records=records,**resources(start)))


if __name__=='__main__':main()
