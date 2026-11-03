#!/usr/bin/env python3
"""One fixed-decision inference job; all eight existing models remain unchanged."""
import argparse
from group_risk import training_split
from exact_conditional_decision import *


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--job',choices=JOBS,required=True)
    parser.add_argument('--check-only',action='store_true');args=parser.parse_args();job=args.job
    start=begin();p=json.loads((OUT/'protocol.json').read_text());assert xgb.__version__==p['xgboost_version']
    d=arrays(CACHE/'input.npz');tr,held,purge=training_split(d,p,job)
    mass=np.array(json.loads((OUT/'proposals.json').read_text())[job]['mass'])
    roles={'held':held} if held is not None else {r:d['role']==r for r in ['train','cal','eval']}
    dest=ART/job;assert not dest.exists()
    report=OUT/job;report.mkdir(parents=True,exist_ok=True)
    if args.check_only:
        for arm in ARMS:
            booster=model(job,arm,p['features']);edges,_=partition(booster)
            xx=query_matrix(d['x'][tr][:2],np.array([5.,6.]),arm)
            assert booster.inplace_predict(xx,predict_type='margin').shape==(2,)
        print(json.dumps(dict(job=job,role_N={r:int(m.sum()) for r,m in roles.items()},
            new_fits=0,formal_point_jobs=0,worker_precreated_directory=True,**resources(start))))
        return
    dest.mkdir(parents=True);(dest/'started.txt').write_text('fixed inference; no restart\n')
    def budget():
        if resources(start)['CPU_s']>850 or resources(start)['wall_s']>1700:
            raise RuntimeError('frozen stage76 resource limit; no shortened candidate or retry')
    output={};records=[]
    for role,take in roles.items():
        output[role+'_row']=d['row'][take]
        output[role+'_true_q_density']=proposal_density(d['pz'][take],np.log(d['truth_E_GeV'][take]),mass)
    for arm in ARMS:
        booster=model(job,arm,p['features']);edges,_=partition(booster);armstart=begin()
        for role,take in roles.items():
            value=predict_exact(booster,d['x'][take],d['pz'][take],mass,arm,chunk=p['chunk_real_X'],budget=budget)
            for key,v in value.items():output[role+'_'+arm+'_'+key]=v
            # Truth is used only for the density score, after the deployment-only decision.
            xx=query_matrix(d['x'][take],np.log(d['truth_E_GeV'][take]),arm)
            true_score=booster.inplace_predict(xx,predict_type='margin').astype(float)
            with np.errstate(divide='ignore'):
                output[role+'_'+arm+'_true_logdensity']=np.log(output[role+'_true_q_density'])+true_score-value['logZ']
            assert np.isfinite(value['raw_log']).all()
        records.append(dict(arm=arm,intervals=len(edges)-1,role_N={r:int(m.sum()) for r,m in roles.items()},
            query_rows=sum(int(m.sum()) for m in roles.values())*(len(edges)-1),
            new_fits=0,truth_not_in_energy_mapping=True,**resources(armstart)))
    budget();np.savez_compressed(dest/'predictions.npz',**output);(dest/'started.txt').unlink()
    save(report/'inference.json',dict(job=job,new_fits=0,formal_point_jobs=1,records=records,
        actual_train_N=int(tr.sum()),purged_N=int(purge.sum()),**resources(start)))
    print((report/'inference.json').read_text())


if __name__=='__main__':main()
