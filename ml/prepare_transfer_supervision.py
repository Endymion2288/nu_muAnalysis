#!/usr/bin/env python3
"""Audit labels, check gradients/masks, measure a bounded pilot and freeze stage69."""
from datetime import datetime,timezone
import json,tempfile,shutil
from pathlib import Path
import numpy as np
import torch
from transfer_supervision import OUT,REPO,configuration,inputs,labels,training_split,transform_state,transform,objective,fit_one,restore,predict,begin,resources,save,masks
from report_expert_combination import table,support


def main():
    start=begin();OUT.mkdir(exist_ok=True);assert not (OUT/'protocol.json').exists()
    old=json.loads((REPO/'workbook/stage68_energy_ml/protocol.json').read_text())
    p=dict(stage=69,starting_commit='1f4fc1c',seed=2026110369,epochs=120,architecture='62 transformed reco +62 missing indicators; shared Linear124x64 SiLU Linear64x64 SiLU, one regression and one three-class auxiliary head; no dropout',
        target='log(E_nu/GeV) minus train mean; no target variance rescale, output add train mean',
        optimizer='AdamW',learning_rate=.001,weight_decay=.0001,batch_size=1024,cpu_threads=1,device='cpu',auxiliary_weight=.1,
        main_loss='mean squared logE error on all training events',auxiliary_loss='sum valid CE / (batch_N * full_train_valid_fraction), unbiased stochastic mean over valid training labels; no class weights',
        labels='confirmed & finite y in[0,1]; y<.2, .2<=y<.8, y>=.8; invalid target -1 masked, all remain in main MSE',
        initialization='same torch seed and zero regression head, start at own-fold train mean; same auxiliary/shared initialization and batch-order seed+1',
        C_auxiliary='present but not optimized, auxiliary logits are not a trained physics classifier; use train-frozen class-prior baseline for P classification',
        feature_policy='F7_pz0_raw_v1',features=configuration()['features'],scaling='same continuous_response transform_state per own training split; train-only log/log1p/asinh, median/IQR, explicit missing mask; no clipping of tails',
        fold_by_group=old['fold_by_group'],fold_counts=old['fold_counts'],fold_identity_purge=True,fold_policy='unchanged stage68 protocol v2, training_split exact incoming purge',
        formal_fits=8,formal_jobs=4,checkpoint='terminal120 only; no early stopping, best-epoch or repair',main_candidate='P_cal',calibration='one global mean log offset per final C/P using8440cal; raw parallel; OOF raw only',
        request_cpus=1,request_memory_MB=3000,request_disk_MB=180,pair_wall_budget_s=2700,pair_cpu_budget_s=2700,total_CPU_budget_s=10800,retained_budget_bytes=20000000,
        bootstrap_seed=2026110369,bootstrap_replicates=500,recovery_ratio_upper95_max=1.05,max_tail50_increase_pp=2.,locked_test=False,new_ROOT_RDO_production=0)
    d=inputs();classes,valid=labels(d)
    assert np.all(~d['confirmed']|(d['primary_valid']&(d['primary_candidates']==1)))
    records=[]
    for role in ['train','cal','eval']:
        rr=d['role']==role
        for key,m in masks(d).items():
            take=rr&m
            records.append(dict(role=role,stratum=key,**support(d,take),aux_valid_N=int((take&valid).sum()),unconfirmed_N=int((take&~d['confirmed']).sum()),invalid_y_confirmed_N=int((take&d['confirmed']&~valid).sum()),**{f'class{k}_N':int((take&(classes==k)).sum()) for k in range(3)}))
    table(OUT/'label_support.tsv',records)
    source=[]
    for role in ['train','cal','eval']:
        for g in np.unique(d['group'][d['role']==role]):
            take=(d['role']==role)&(d['group']==g)
            source.append(dict(role=role,group=str(g),N=int(take.sum()),valid_N=int((take&valid).sum()),**{f'class{k}_N':int((take&(classes==k)).sum()) for k in range(3)}))
    table(OUT/'label_sources.tsv',source)
    ratio=(1-d['y_lepton'][valid])*d['truth_E_GeV'][valid];mass2=ratio**2-d['primary_p_GeV'][valid]**2
    save(OUT/'truth_label_audit.json',dict(y_definition='frozen_evaluation.truth_diagnostics:1-E_primary_mu_production/E_incoming; all energies GeV; primary unique same production vertex within1e-4mm, lead barcode/pdg and incoming parent barcode/pdg confirmed',confirmed_implies_unique_primary=True,
        confirmed_invalid_y_N=int((d['confirmed']&~valid).sum()),valid_N=int(valid.sum()),inferred_mu_mass2_GeV2_min=float(mass2.min()),inferred_mu_mass2_GeV2_median=float(np.median(mass2)),inferred_mu_mass2_GeV2_max=float(mass2.max()),
        primary_E_minus_p_GeV_min=float(np.min(ratio-d['primary_p_GeV'][valid])),primary_E_minus_p_GeV_max=float(np.max(ratio-d['primary_p_GeV'][valid])),truth_labels_are_not_reco_inputs=True))
    # Known boundaries, ignored unconfirmed labels and exact full-population CE normalization.
    toy=dict(y_lepton=np.array([0.,.2,.8,1.,-.01,1.01,np.nan,.5]),confirmed=np.array([1,1,1,1,1,1,1,0],bool))
    cc,vv=labels(toy);np.testing.assert_array_equal(cc,[0,1,2,2,-1,-1,-1,-1])
    pred=torch.tensor([.1,.5,-.2,.8],dtype=torch.float64,requires_grad=True);logits=torch.tensor([[.3,.1,-.2],[0.,.4,-.3],[.1,.2,.3],[.5,-.1,.2]],dtype=torch.float64,requires_grad=True)
    target=torch.tensor([.2,.2,-.1,.9],dtype=torch.float64);cls=torch.tensor([0,-1,2,-1]);vm=cls>=0
    loss,_,_=objective(pred,logits,target,cls,vm,.1,.5);loss.backward()
    expected_grad=2*(pred.detach()-target)/4;torch.testing.assert_close(pred.grad,expected_grad)
    expected_logits=torch.zeros_like(logits);expected_logits[vm]=.1/2*(torch.softmax(logits.detach()[vm],dim=1)-torch.nn.functional.one_hot(cls[vm],3));torch.testing.assert_close(logits.grad,expected_logits)
    batch_losses=[]
    for idx in [torch.tensor([0,1]),torch.tensor([2,3])]:batch_losses.append(objective(pred.detach()[idx],logits.detach()[idx],target[idx],cls[idx],vm[idx],.1,.5)[0])
    torch.testing.assert_close(torch.stack(batch_losses).mean(),loss.detach())
    tr=d['role']=='train';chosen=np.flatnonzero(tr)[:512];small={k:v[chosen] for k,v in d.items()};sc,sv=labels(small);state=transform_state(small['x']);xx,_=transform(small['x'],state);assert xx.shape==(512,124) and np.isfinite(xx).all()
    scratch=Path(tempfile.mkdtemp(prefix='transfer69_pilot_'));pilot={};initials=[]
    try:
        for family in ['C','P']:
            model,initial,diag=fit_one(small['x'],np.log(small['truth_E_GeV']),sc,sv,state,p,family,scratch,epochs=5);initials.append(initial);pilot[family]={k:v for k,v in diag.items() if k!='history'}
            restored,meta=restore(scratch/(family+'.pt'));a,pr=predict(model,small['x'],state,diag['target_center']);b,pr2=predict(restored,small['x'],meta['feature_state'],meta['target_center']);np.testing.assert_array_equal(a,b);np.testing.assert_array_equal(pr,pr2)
        for key in initials[0]:torch.testing.assert_close(initials[0][key],initials[1][key],rtol=0,atol=0)
    finally:shutil.rmtree(scratch)
    folds=[]
    for job in ['fold0','fold1','fold2','final']:
        take,held,purge=training_split(d,p,job);folds.append(dict(job=job,train_N=int(take.sum()),aux_valid_N=int((take&valid).sum()),class_N=[int((take&(classes==k)).sum()) for k in range(3)],held_N=int(held.sum()) if held is not None else 0,purged_N=int(purge.sum())))
    p.update(frozen_utc=datetime.now(timezone.utc).isoformat(),fold_label_counts=folds,pilot_N=512,pilot_epochs=5,pilot_fits_not_candidates=2,torch_version=torch.__version__)
    save(OUT/'pilot.json',dict(**resources(start),families=pilot,boundary_mask_gradient_and_normalization_checks=True,identical_initial_states=True,standalone_reload_exact=True,retained_pilot_models=0))
    save(OUT/'protocol.json',p);print(json.dumps(folds,indent=2));print('pilot pair CPU',sum(v['resources']['cpu_s'] for v in pilot.values()))


if __name__=='__main__':main()
