#!/usr/bin/env python3
"""One immutable stage69 C/P pair; model frozen before held/cal/eval inference."""
import argparse,json,traceback
from datetime import datetime,timezone
import numpy as np
import torch
from transfer_supervision import OUT,ART,inputs,labels,training_split,transform_state,fit_one,predict,begin,resources,save
from report_expert_combination import table


def main(job):
    start=begin();p=json.loads((OUT/'protocol.json').read_text());dest=ART/job;record=OUT/job
    assert not dest.exists() and not record.exists(),'No repeated started or successful formal pair'
    record.mkdir();save(record/'status.json',dict(status='started',job=job,utc=datetime.now(timezone.utc).isoformat()))
    d=inputs();use,held,purge=training_split(d,p,job);dd={k:v[use] for k,v in d.items()};classes,valid=labels(dd);state=transform_state(dd['x']);y=np.log(dd['truth_E_GeV'])
    priors=np.bincount(classes[valid],minlength=3)/valid.sum();assert np.all(priors>0)
    arrays={};summaries={};history=[];initial_C=None
    for family in ['C','P']:
        model,initial,diag=fit_one(dd['x'],y,classes,valid,state,p,family,dest)
        if family=='C':initial_C=initial
        else:
            for k in initial_C:torch.testing.assert_close(initial_C[k],initial[k],rtol=0,atol=0)
        for row in diag.pop('history'):history.append(dict(family=family,**row))
        diag['frozen_before_held_inference_utc']=datetime.now(timezone.utc).isoformat();summaries[family]=diag
        for role,take in ([('held',held)] if held is not None else [(r,d['role']==r) for r in ['train','cal','eval']]):
            pred,prob=predict(model,d['x'][take],state,diag['target_center'])
            arrays[role+'_row']=d['row'][take];arrays[role+'_'+family+'_raw_log']=pred
            if family=='P':arrays[role+'_P_prob']=prob
        assert time_ok(start,p)
    np.savez_compressed(dest/'predictions.npz',**arrays)
    table(record/'history.tsv',history)
    save(record/'fit.json',dict(job=job,status='completed',formal_fits=2,train_N=int(use.sum()),auxiliary_valid_N=int(valid.sum()),class_N=np.bincount(classes[valid],minlength=3).tolist(),train_class_prior=priors.tolist(),held_N=int(held.sum()) if held is not None else 0,purged_N=int(purge.sum()),train_groups=sorted(set(d['group'][use])),held_groups=sorted(set(d['group'][held])) if held is not None else [],families=summaries,identical_initialization_and_batch_order=True,whole_job_resources=resources(start)))
    (record/'status.json').unlink();print(job,json.dumps(summaries,indent=2),flush=True)


def time_ok(start,p):
    r=resources(start);return r['wall_s']<p['pair_wall_budget_s'] and r['cpu_s']<p['pair_cpu_budget_s']


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--job',choices=['fold0','fold1','fold2','final'],required=True);a=parser.parse_args()
    try:main(a.job)
    except Exception:
        (OUT/('failure_'+a.job+'.txt')).write_text(traceback.format_exc());raise
