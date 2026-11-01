#!/usr/bin/env python3
"""Branch-clipped track features on frozen IDs, or bounded data MIP proxy."""
import argparse
import csv
import json
import resource
import time
from pathlib import Path
import awkward as ak
import numpy as np
import uproot
from track_response import TRACK_BRANCHES, configuration, derive, profile


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--batch',type=int,default=0);p.add_argument('--index',type=int)
    p.add_argument('--data',action='store_true');p.add_argument('--tracker-control',action='store_true');p.add_argument('--entry-stop',type=int)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();cfg=configuration(a.repo);tick=time.perf_counter();cpu=time.process_time()
    branches=['run','eventID','Track_PropagationError']+TRACK_BRANCHES
    reports=[];sets=[]
    if a.data:
        extra=['Track_nLayers','Track_nDoF','Track_Chi2','Track_r_atMaxRadius',
               'VetoNu0_charge','VetoNu1_charge']+[f'{prefix}{i}_{suffix}' for prefix in ['CaloHi','CaloLo'] for i in range(4) for suffix in ['nMIP','charge','status']]
        with uproot.open(cfg['data_control']['input']) as source:
            tree=source['nt'];arr=tree.arrays(branches+extra,entry_stop=a.entry_stop or cfg['data_control']['entry_stop'])
        masks=[('input',np.ones(len(arr),bool))]
        # Require exactly one saved track; padding is used only for the cutflow.
        def first(k):return ak.to_numpy(ak.fill_none(ak.firsts(arr[k]),np.nan))
        cuts=[('one_saved_track',ak.to_numpy(ak.num(arr['Track_p0'])==1)),
              ('pz_gt100GeV',first('Track_pz0')>100000),('layers_ge7',first('Track_nLayers')>=7),
              ('ndof_ge9',first('Track_nDoF')>=9),('chi2ndof_lt15',first('Track_Chi2')/np.maximum(first('Track_nDoF'),1)<15),
              ('rmax_lt95mm',first('Track_r_atMaxRadius')<95),
              ('veto_MIP',ak.to_numpy((arr['VetoNu0_charge']>40)&(arr['VetoNu1_charge']>40)))]
        calo=np.ones(len(arr),bool)
        for i in range(4):calo &= ak.to_numpy((arr[f'CaloHi{i}_nMIP']>.5)&(arr[f'CaloHi{i}_nMIP']<2))
        cuts.append(('calo_MIP',calo));mask=np.ones(len(arr),bool)
        for key,cut in cuts:mask &= cut;masks.append((key,mask.copy()))
        chosen=masks[-2][1] if a.tracker_control else mask
        data=derive(arr[chosen],cfg['features'],False);sets.append(data)
        reports.append(dict(input=cfg['data_control']['input'],input_events=len(arr),selected_events=int(chosen.sum()),tracker_only_control=a.tracker_control,
                            calo_profile=profile({k:ak.to_numpy(arr[k][chosen]) for k in extra if k.startswith('Calo')},[k for k in extra if k.startswith('Calo')]),
                            cutflow={k:int(m.sum()) for k,m in masks},profile=profile(data,cfg['features'])))
    else:
        rows=[r for r in csv.DictReader((a.repo/'ml/configs/files.tsv').open(),delimiter='\t') if r['partition'] in cfg['partitions']]
        rows=[r for r in rows if int(r['index'])==a.index] if a.index is not None else rows[a.batch*cfg['batch_size']:(a.batch+1)*cfg['batch_size']]
        selected={}
        for part in cfg['partitions']:
            with np.load(a.repo/f'ntuples/energy_ml_stage12/dataset/{part}.npz') as z:
                selected[part]={k:z[k] for k in ['eventID','manifest_index']}
        for row in rows:
            start=time.perf_counter();old=selected[row['partition']]
            wanted=old['eventID'][old['manifest_index']==int(row['index'])]
            with uproot.open(row['input']) as source:
                tree=source['nt'];ids=tree['eventID'].array(library='np');mask=np.isin(ids,wanted)
                if int(mask.sum())!=len(wanted) or len(wanted)!=int(row['expected_selected']):raise RuntimeError('Selected ID mismatch')
                arr=tree.arrays(branches+['Track_isForward'])[mask]
            data=derive(arr,cfg['features']);data['manifest_index']=np.full(len(arr),int(row['index']),dtype='int32')
            order=np.argsort(data['eventID']);data={k:v[order] for k,v in data.items()}
            np.testing.assert_array_equal(data['eventID'],np.sort(wanted));sets.append(data)
            report=dict(index=int(row['index']),input=row['input'],input_events=len(ids),selected_events=len(arr),wall_s=time.perf_counter()-start)
            reports.append(report);print(json.dumps(report),flush=True)
    result={k:np.concatenate([d[k] for d in sets]) for k in sets[0]}
    meta=dict(reports=reports,wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cpu,
              peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
              profile=profile(result,cfg['features']),cfg=cfg,data_control=a.data)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(a.output,**result,metadata_json=np.array(json.dumps(meta)))
    print(json.dumps(meta),flush=True)

if __name__=='__main__':main()
