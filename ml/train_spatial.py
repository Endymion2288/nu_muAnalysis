#!/usr/bin/env python3
"""Fixed-capacity station-information ablation, with a within-event null."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path

import numpy as np
import torch
import yaml

from extract_spatial import feature_names
from train_bdt import check_features, load, metric_values, write_table
from train_tabular import fit_bdt, preprocess


def inputs(base,spatial,cfg):
    counts,moments=feature_names()
    additions={name:spatial['counts'][:,i] for i,name in enumerate(counts)}
    additions.update({name:spatial['moments'][:,i] for i,name in enumerate(moments)})
    tangent=[]
    for s,center in enumerate(cfg['station_centers_mm']):
        for i,axis in enumerate('xy'):
            name=f'SP_s{s}_delta_tangent_{axis}_mm';tangent.append(name)
            reference=base[f'ML_mu_{axis}0_mm']+(center-base['ML_mu_z0_mm'])*base[f'ML_mu_p{axis}0_GeV']/(base['LeadTrack_pz0']/1000)
            additions[name]=spatial['moments'][:,s*5+i]-reference
    return additions,counts,moments,tangent


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--cache-root',type=Path,help='Repository containing the frozen event caches; defaults to --repo')
    p.add_argument('--seed-index',type=int,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--smoke',action='store_true')
    args=p.parse_args();repo=args.repo;out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    tick=time.perf_counter();cpu=time.process_time();torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    cfg=yaml.safe_load((repo/'ml/configs/spatial.yaml').read_text());baseline=yaml.safe_load((repo/'ml/configs/baseline.yaml').read_text())
    rows=list(csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t'))
    train,tgroups=load(rows,baseline,'train');val,groups=load(rows,baseline,'validation');assert not set(tgroups)&set(groups)
    data=[];sp=[]
    for part,base,n in [('train',train,1200),('validation',val,400)]:
        with np.load((args.cache_root or repo)/f'ntuples/energy_ml_stage18/{part}.npz') as d:
            assert json.loads(str(d['config_json']))==cfg
            for k in ['run','eventID']:np.testing.assert_array_equal(d[k],base[k])
            spatial={k:d[k] for k in d.files if not k.endswith('_json')}
        if args.smoke:
            base={k:v[:n] for k,v in base.items()};spatial={k:v[:n] for k,v in spatial.items()}
        additions,counts,moments,tangent=inputs(base,spatial,cfg)
        data.append(dict(**base,**additions));sp.append(spatial)
    train,val=data
    if args.smoke:groups=groups[:400]
    original=sum([baseline['feature_groups'][g] for g in baseline['feature_versions']['F5']],[])
    versions=dict(F5=original,counts=original+counts,moments=original+counts+moments,
                  centroids=original+counts+[m for m in moments if 'mean_' in m],
                  widths=original+counts+[m for m in moments if 'mean_' not in m],
                  tangent=original+counts+moments+tangent,reassigned=original+counts+moments)
    target=np.log(train[baseline['target']]);y=val[baseline['target']];center=float(target.mean());spread=float(target.std())
    yt=((target-center)/spread).astype('float32');yv=((np.log(y)-center)/spread).astype('float32')
    predictions={};costs=[];traces={};preprocessors={};metrics=[]
    for name in cfg['models']:
        names=versions[name];check_features(names,original+counts+moments+tangent)
        matrices=[]
        for i,base in enumerate(data):
            x=np.column_stack([base[k] for k in names])
            if name=='reassigned':x[:,-20:]=sp[i][f'reassigned_{args.seed_index}']
            matrices.append(x)
        xt,xv,state=preprocess(*matrices)
        trial=dict(max_depth=cfg['xgboost']['max_depth'],rounds=cfg['xgboost']['rounds'])
        study=dict(max_trial_wall_s=180,bdt_patience=cfg['xgboost']['patience'])
        raw,cost,trace,model=fit_bdt(trial,baseline,study,cfg['seeds'][args.seed_index],xt,xv,yt,yv,args.smoke)
        if args.smoke:cost['stop_reason']='smoke_rounds'
        predictions[name]=np.exp(raw.astype(float)*spread+center)
        costs.append(dict(model=name,seed=cfg['seeds'][args.seed_index],features=len(names),**cost))
        traces[name]=trace;preprocessors[name]=dict(features=names,preprocessor=state,target_center=center,target_spread=spread)
        metrics.append(dict(model=name,**metric_values(y,predictions[name],np.ones(len(y),dtype=bool))))
        if args.seed_index==0:model.save_model(out/f'{name}.ubj')
        print(json.dumps(costs[-1]),flush=True)
    np.savez_compressed(out/'predictions.npz',run=val['run'],eventID=val['eventID'],truth_E_GeV=y,group=groups,**predictions)
    write_table(out/'costs.tsv',costs);write_table(out/'metrics.tsv',metrics)
    (out/'learning_traces.json').write_text(json.dumps(traces)+'\n')
    if args.seed_index==0:(out/'preprocessing.json').write_text(json.dumps(preprocessors)+'\n')
    summary=dict(seed_index=args.seed_index,seed=cfg['seeds'][args.seed_index],smoke=args.smoke,study=cfg,
                 train_events=len(yt),validation_events=len(y),gpu=torch.cuda.get_device_name(0),
                 wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
                 peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,calibration_test_challenge_evaluated=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
