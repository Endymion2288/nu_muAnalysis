#!/usr/bin/env python3
"""Separate depth predictability from energy utility, with matched training priors."""
import json
from pathlib import Path
import numpy as np
from coarse_depth import REPO,load_inputs,region_labels
from report_calonu_information import source_draws,strata
from train_bdt import write_table


def losses(q,labels,floor):
    return -np.log(np.maximum(q[np.arange(len(labels)),labels],floor)),np.sum((q-np.eye(5)[labels])**2,axis=1)


def metrics(q,labels,floor):
    log,brier=losses(q,labels,floor);conf=np.zeros((5,5),int);np.add.at(conf,(labels,q.argmax(axis=1)),1)
    counts=conf.sum(axis=1);recall=np.divide(conf.diagonal(),counts,out=np.full(5,np.nan),where=counts>0)
    return dict(N=len(labels),log_score=float(log.mean()),Brier=float(brier.mean()),accuracy=float((q.argmax(axis=1)==labels).mean()),
                macro_recall=float(np.nanmean(recall))),conf,recall


def main():
    rows,d,x=load_inputs();cfg=json.loads((REPO/'ml/configs/coarse_depth.json').read_text());floor=cfg['probability_floor_for_scoring']
    labels=region_labels(d['vertex_z_mm'],cfg['regions_mm']);q=np.full((len(rows),5),np.nan);prior=q.copy();roles=[]
    for f in range(3):
        with np.load(REPO/f'ml/artifacts/stage45/formal/{f}/predictions.npz') as z:
            md=json.loads(str(z['metadata_json']));assert md['config']==cfg
            ids=np.flatnonzero(d['fold']==f);np.testing.assert_array_equal(z['cache_row'],rows[ids]);q[ids]=z['depth_q'];prior[ids]=z['depth_prior']
            for role,rr,values,pp in [('train_OOF',z['train_cache_row'],z['depth_train_oof'],z['depth_train_prior']),
                                      ('cal',z['cal_cache_row'],z['depth_cal'],z['depth_prior']),('eval',z['cache_row'],z['depth_q'],z['depth_prior'])]:
                pos=np.searchsorted(rows,rr);np.testing.assert_array_equal(rows[pos],rr)
                for name,v in [('depth',values),('training_prior',np.broadcast_to(pp,(len(pos),5)))]:
                    met,_,_=metrics(v,labels[pos],floor);roles.append(dict(fold=f,role=role,model=name,**met))
    assert np.isfinite(q).all();unique,gid,draws=source_draws(d,cfg['bootstrap_replicates'],cfg['seed']);ng=len(unique)
    results=[];paired=[];confusions=[];lq,bq=losses(q,labels,floor);lp,bp=losses(prior,labels,floor)
    for label,mask in strata(d).items():
        if not mask.any():continue
        for name,v in [('depth',q),('training_prior',prior)]:
            met,conf,recall=metrics(v[mask],labels[mask],floor);results.append(dict(stratum=label,model=name,**met))
            confusions.append(dict(stratum=label,model=name,true_region_N=conf.sum(axis=1).tolist(),confusion_true_rows_pred_columns=conf.tolist(),
                                   recall=[float(v) if np.isfinite(v) else None for v in recall]))
        counts=np.bincount(gid,weights=mask,minlength=ng);den=draws@counts;ok=den>0
        a=draws[ok]@np.bincount(gid,weights=mask*(lq-lp),minlength=ng)/den[ok]
        b=draws[ok]@np.bincount(gid,weights=mask*(bq-bp),minlength=ng)/den[ok]
        paired.append(dict(stratum=label,N=int(mask.sum()),log_score_delta=float((lq-lp)[mask].mean()),CI025=float(np.quantile(a,.025)),CI975=float(np.quantile(a,.975)),
                           Brier_delta=float((bq-bp)[mask].mean()),Brier_CI025=float(np.quantile(b,.025)),Brier_CI975=float(np.quantile(b,.975))))
    out=REPO/'workbook/stage45_energy_ml'
    write_table(out/'depth_metrics.tsv',results);write_table(out/'depth_paired.tsv',paired);write_table(out/'depth_role_metrics.tsv',roles)
    (out/'depth_confusion.json').write_text(json.dumps(confusions,indent=2)+'\n')
    np.savez_compressed(REPO/'ntuples/energy_ml_stage45/depth_predictions.npz',cache_row=rows,depth_q=q,depth_prior=prior,region=labels)
    print(json.dumps(next(r for r in paired if r['stratum']=='focus')))


if __name__=='__main__':main()
