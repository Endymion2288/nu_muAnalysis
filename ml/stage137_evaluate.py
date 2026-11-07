"""Paired conditional energy/tail risks; oracle attribution has an unsplit control."""
import json
import numpy as np
from stage119_curve_common import LAYERS
from stage119_reportcurve import ci,metrics
from stage137_common import OUT,CACHE,ART,load,table,protocol,evaluation_masks

def bootstrap(d,role):
    ix=np.flatnonzero(d['role']==role)
    return ix,load('ntuples/energy_ml_stage131/bootstrap_draws.npz')[f'role{role}']

def main():
    d=load('ntuples/energy_ml_stage131/matched_input.npz');p=protocol();pred=load(ART/'energy_predictions.npz');names=list(pred);arms=list(p['arms']);points=[];pairs=[];supports=[];gates=[];powers=[]
    contrasts=[tuple(v) for v in p['comparisons']]+[('AK','A'),('A','X'),('F','U')]+[(a,b) for a in arms for b in ['direct_cal','traditional']]
    boots={}
    for role in [2,3]:
        ix,draw=bootstrap(d,role);boots[f'role{role}']=draw
        sd={k:v[ix] for k,v in d.items()};layers=evaluation_masks(sd)
        for layer,mask in layers.items():
            rows=ix[mask];w=d['weight'][rows];b=draw[:,mask]*w
            if not len(rows):continue
            den=b.sum(1);valid=den>0
            error=np.column_stack([pred[name][rows]-np.log(d['truth_E_GeV'][rows]) for name in names]);assert np.isfinite(error).all()
            sq=b@(error**2);central=np.average(error**2,weights=w,axis=0);rel=np.expm1(error)
            support=dict(role=role,stratum=layer,N=len(rows),incoming=len(rows),weight_sum=float(w.sum()),ESS=float(w.sum()**2/(w@w)))
            supports.append(support)
            for j,name in enumerate(names):
                lo,hi=ci(np.sqrt(sq[valid,j]/den[valid]));points.append(dict(**support,model=name,**metrics(error[:,j],w),RMSE_low95=lo,RMSE_high95=hi))
            tails={s:(np.average(flag,weights=w,axis=0),b@flag) for s,flag in [('total',abs(rel)>.5),('positive',rel>.5),('negative',rel<-.5)]}
            for candidate,reference in contrasts:
                j,k=names.index(candidate),names.index(reference);good=valid&(sq[:,k]>0);lo,hi=ci(np.sqrt(sq[good,j]/sq[good,k]))
                r=dict(**support,candidate=candidate,reference=reference,RMSE_ratio=float(np.sqrt(central[j]/central[k])),low95=lo,high95=hi)
                for sign,(v,bs) in tails.items():
                    lo,hi=ci(100*(bs[good,j]-bs[good,k])/den[good]);r.update({sign+'_tail_delta_pp':float(100*(v[j]-v[k])),sign+'_tail_low95_pp':lo,sign+'_tail_high95_pp':hi})
                pairs.append(r)
                if (candidate,reference) in contrasts[:9] and layer in LAYERS:
                    contrast=error[:,j]**2-.9025*error[:,k]**2;mean=np.average(contrast,weights=w);variance=np.average((contrast-mean)**2,weights=w);delta=.0975*central[k]
                    powers.append(dict(role=role,stratum=layer,candidate=candidate,reference=reference,target_RMSE_ratio=.95,current_incoming=len(rows),current_ESS=support['ESS'],normal80pct_ESS=float((1.95996398454+.84162123357)**2*variance/delta**2) if delta>0 else None,scope='conditional paired-loss weighted normal approximation,not guarantee or source/system/refitpower'))
        for arm in arms:
            for layer in LAYERS:
                ref='traditional' if layer in LAYERS[:2] else 'direct_cal';limit=1.05 if ref=='traditional' else 1.01 if layer=='all' else 1.03
                r=next((r for r in pairs if r['role']==role and r['stratum']==layer and r['candidate']==arm and r['reference']==ref),None)
                t=next((r for r in pairs if r['role']==role and r['stratum']==layer and r['candidate']==arm and r['reference']=='direct_cal'),None)
                gates.append(dict(role=role,arm=arm,stratum=layer,RMSE_upper95=r['high95'] if r else None,limit=limit,RMSE_pass=bool(r and r['high95'] is not None and r['high95']<=limit),tail_pass=bool(t and all(t[s+'_tail_high95_pp'] is not None and t[s+'_tail_high95_pp']<=2 for s in ['total','positive','negative']))))
    np.savez_compressed(CACHE/'bootstrap_draws.npz',**boots)
    for name,rows in [('metrics',points),('paired',pairs),('support',supports),('gates',gates),('conditional_power',powers)]:table(name+'.tsv',rows)
    joint={f'{role}_{arm}':all(g['RMSE_pass'] and g['tail_pass'] for g in gates if g['role']==role and g['arm']==arm) for role in [2,3] for arm in arms}
    continuation={}
    for candidate,reference in contrasts[:9]:
        rows=[r for r in pairs if r['candidate']==candidate and r['reference']==reference and r['stratum'] in LAYERS[:2]]
        continuation[candidate+'/'+reference]=len(rows)==4 and all(r['high95'] is not None and r['high95']<1 and r['RMSE_ratio']<=.95 for r in rows)
    summary=dict(joint=joint,mechanism_two_lowbins_cal_and_test_5pct=continuation,promotion=False,reserve_predictions=0,independent_confirmation=False,scope='same-support conditional oldselected/reselected cohort,HTinverse-inclusion target; fixedmodel,within samplingstratum×component incomingbootstrap; no source/refit/GENIE/system/researchselection or simultaneous95coverage')
    (OUT/'energy_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary)

if __name__=='__main__':main()
