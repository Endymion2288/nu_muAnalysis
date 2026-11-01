#!/usr/bin/env python3
"""Freeze new source groups, prioritizing the selected 100--250 GeV region."""
import argparse,csv,json,time
from pathlib import Path
import numpy as np
import uproot,yaml
from train_bdt import write_table

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);args=parser.parse_args()
    repo=args.repo;tick=time.perf_counter();cfg=yaml.safe_load((repo/'ml/configs/low_momentum_audit.yaml').read_text())
    rng=np.random.default_rng(cfg['seed']);rows=list(csv.DictReader((repo/'ml/configs/files.tsv').open(),delimiter='\t'))
    old={r['group'] for r in csv.DictReader((repo/cfg['exclude_manifest']).open(),delimiter='\t')}
    sets={};population=[];chosen=[]
    for part in cfg['partitions']:
        with np.load(repo/f'ntuples/energy_ml_stage12/dataset/{part}.npz') as z:base={k:z[k] for k in z.files if k!='config_json'}
        with np.load(repo/f'ntuples/energy_ml_stage15/{part}_truth.npz') as z:truth={k:z[k] for k in z.files if k!='config_json'}
        for key in ['run','eventID']:np.testing.assert_array_equal(base[key],truth[key])
        sets[part]=(base,truth)
        for lo,hi in zip(cfg['truth_p_edges_GeV'][:-1],cfg['truth_p_edges_GeV'][1:]):
            mask=(truth['primary_p_GeV']>=lo)&(truth['primary_p_GeV']<hi)
            population.append(dict(partition=part,p_low_GeV=lo,p_high_GeV=hi,N=int(mask.sum()),confirmed=int((mask&truth['lead_primary_parent_confirmed']).sum())))
    for comp in cfg['components']:
        for part in cfg['partitions']:
            groups=sorted({r['group'] for r in rows if r['component']==comp and r['partition']==part}-old)[:cfg['new_groups_per_component_partition']]
            assert len(groups)==cfg['new_groups_per_component_partition']
            chosen.extend(r for r in rows if r['partition']==part and r['group'] in groups)
    output=repo/f"ntuples/energy_ml_stage{cfg['stage']}/requests";output.mkdir(parents=True,exist_ok=True)
    report=repo/f"workbook/stage{cfg['stage']}_energy_ml";report.mkdir(parents=True,exist_ok=True)
    manifest=[];sample=[]
    for row in chosen:
        base,t=sets[row['partition']];available=np.flatnonzero(base['manifest_index']==int(row['index']));selected=[];cov=[];pools=[]
        # Round-robin nonempty y/z/charge cells within each momentum quota.
        for lo,hi,quota,ncov in zip(cfg['sampling_p_edges_GeV'][:-1],cfg['sampling_p_edges_GeV'][1:],cfg['truth_quotas'],cfg['covariance_quotas']):
            indices=available[(t['primary_p_GeV'][available]>=lo)&(t['primary_p_GeV'][available]<hi)];cells={}
            for idx in rng.permutation(indices):
                key=(int(np.searchsorted(cfg['y_edges'],t['y_lepton'][idx],side='right')-1),int(np.searchsorted(cfg['vertex_z_edges_mm'],t['vertex_z_mm'][idx],side='right')-1),int(np.sign(t['primary_pdg'][idx])))
                cells.setdefault(key,[]).append(int(idx))
            take=[]
            while len(take)<min(quota,len(indices)):
                keys=[key for key,v in cells.items() if v];rng.shuffle(keys)
                for key in keys:
                    if len(take)==min(quota,len(indices)):break
                    take.append(cells[key].pop())
            assert len(take)>=ncov,(row['index'],lo,len(take))
            cov.extend(int(i) for i in rng.choice(take,size=ncov,replace=False));selected.extend(take)
            pools.append((int(lo),len(indices),len(take),ncov))
        if len(selected)<cfg['truth_events_per_file']:
            # Predetermined fallback fills only truth quota, never changes cov slots.
            extra=available[(t['primary_p_GeV'][available]>=100)&~np.isin(available,selected)]
            selected.extend(int(i) for i in rng.choice(extra,size=cfg['truth_events_per_file']-len(selected),replace=False))
        with uproot.open(row['input']) as f:ids=f['nt']['eventID'].array(library='np')
        lookup={int(e):i for i,e in enumerate(ids)};events=[]
        for idx in selected:
            e={k:t[k][idx].item() for k in ['run','eventID','primary_pdg','primary_barcode','primary_p_GeV','primary_px','primary_py','primary_pz','vertex_x_mm','vertex_y_mm','vertex_z_mm','truth_E_GeV','y_lepton','lead_primary_parent_confirmed']}
            e.update(entry=lookup[int(e['eventID'])],covariance_requested=idx in cov,group=row['group'],partition=row['partition'])
            e['reco_front']=[float(base[f'ML_mu_{x}0_mm'][idx]) for x in ['x','y','z']]+[float(base['ML_mu_px0_GeV'][idx]*1000),float(base['ML_mu_py0_GeV'][idx]*1000),float(base['LeadTrack_pz0'][idx]*1000)]
            e['reco_p_GeV']=float(base['ML_mu_p_GeV'][idx]);e['reco_charge']=int(base['LeadTrack_charge'][idx]);events.append(e)
            sample.append(dict(index=row['index'],**{key:e[key] for key in ['run','eventID','group','partition','truth_E_GeV','primary_p_GeV','y_lepton','vertex_z_mm','lead_primary_parent_confirmed','covariance_requested']}))
        request=dict(row=row,cfg=cfg,events=events,sampling_cells=pools)
        (output/f"{row['index']}.json").write_text(json.dumps(request,separators=(',',':'))+'\n')
        manifest.append(dict(index=row['index'],run=row['run'],group=row['group'],partition=row['partition'],events=len(events),covariance_events=len(cov),input_rdo=row['input_rdo']))
    assert len(cov)==cfg['covariance_events_per_file']
    assert sum(r['covariance_events'] for r in manifest)<=cfg['max_reconstruction_events']
    write_table(report/'manifest.tsv',manifest);write_table(report/'sample.tsv',sample);write_table(report/'selected_population.tsv',population)
    summary=dict(files=len(chosen),groups=len({r['group'] for r in manifest}),events=len(sample),covariance_events=sum(r['covariance_events'] for r in manifest),wall_s=time.perf_counter()-tick,source_groups_disjoint_from_stage32=True)
    (report/'preparation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
