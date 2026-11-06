"""Matched cumulative response information experiment, fixed capacity and roles."""
import csv
import gzip
import json
import multiprocessing as mp
import resource
import time
from pathlib import Path

import numpy as np
import xgboost as xgb

from stage119_curve_common import masks,weights,LAYERS
from stage119_reportcurve import metrics,ci

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage122_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage122';ART=ROOT/'ml/artifacts/stage122'


def table(name,rows):
    if not rows:return
    names=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=names,delimiter='\t');w.writeheader();w.writerows(rows)


def load(path):
    with np.load(path) as z:return {k:z[k] for k in z.files if k!='metadata_json'}


def prepare():
    d=load(CACHE/'cohort_input.npz');p=json.loads((OUT/'cohort_contract.json').read_text());B=[];C=[];D=[];coverage=[];cost=[];checks=[]
    edges=[0,40,80,160,320,640,1200]
    for i,source in enumerate(p['sources']):
        with gzip.open(CACHE/f'cohort_{i}.json.gz','rt') as f:r=json.load(f)
        pos=np.flatnonzero(d['source_index']==source['source_index']);assert len(r['events'])==len(pos)
        assert [x['entry'] for x in r['events']]==d['input_entry'][pos].tolist()
        assert [x['event'] for x in r['events']]==d['eventID'][pos].tolist()
        np.testing.assert_array_equal(np.array([x['incoming'] for x in r['events']],dtype='float32'),d['incoming'][pos].astype('float32'))
        np.testing.assert_allclose([x['E_GeV'] for x in r['events']],d['truth_E_GeV'][pos],rtol=2e-6,atol=1e-6)
        for j,row in enumerate(r['events']):
            b=[];c=[];dd=[]
            for detector,plate in [('VetoNu',0),('VetoNu',1),('Preshower',0)]:
                channel=f'{detector}{plate}';det=row['detectors'][detector]
                hardware_channel=4+plate if detector=='VetoNu' else 12
                waves=[w for w in det['saved'] if w['channel']==hardware_channel];assert len(waves)<=1
                timing=next(t for t in det['timing'] if t['station']==0 and t['plate']==plate)
                energy=np.asarray(timing['energy_MeV']);assert len(energy)==11 and np.all(energy>=0)
                # C must not reveal counts from outside the input window.
                # The saved total hit count includes late deposits: use only
                # in-window energy and its zero indicator here.
                inside=float(energy[1:8].sum())
                c.extend(np.log1p(energy[1:8]));c.extend([np.log1p(inside),int(inside==0)])
                dd.extend(np.log1p(energy[[0,8,9,10]]))
                if waves:
                    adc=np.asarray(waves[0]['adc'],float);assert adc.shape==(600,)
                    baseline=adc[:20].mean();residual=baseline-adc
                    b.extend([2*residual[lo//2:hi//2].sum() for lo,hi in zip(edges,edges[1:])])
                    b.extend([baseline,adc[:20].std(),np.mean(adc==0),1])
                    saturation=int(np.any(adc==0))
                else:b.extend([np.nan]*9+[0]);saturation=0
                coverage.append(dict(source_index=source['source_index'],role=int(d['role'][pos[j]]),environment=source['environment'],channel=channel,present=int(bool(waves)),saturated=saturation,
                    no_sensitive_hits=int(timing['hits']==0),inside_MeV=float(energy[1:8].sum()),outside_MeV=float(energy[[0,8,9,10]].sum()),parent_N=1))
            B.append(b);C.append(c);D.append(dd)
        cost.append(dict(index=i,source_index=source['source_index'],N=len(pos),CPU_s=r['CPU_s'],wall_s=r['wall_s'],RSS_KiB=r['RSS_KiB'],read_bytes=r['read_bytes']))
        checks.append(dict(source_index=source['source_index'],N=len(pos),run_event_incoming_equal=True,truth_energy_rtol=2e-6))
    d.update(B=np.array(B,dtype='float32'),C=np.array(C,dtype='float32'),D=np.array(D,dtype='float32'))
    assert len(d['B'])==len(d['x'])
    # Native reader and input arrays traverse identical frozen source/entry order.
    assert np.array_equal(d['source_index'],np.sort(d['source_index']))
    d['pz']=d['reco_pz_GeV'];np.savez_compressed(CACHE/'comparison_input.npz',**d)
    table('native_cost.tsv',cost);table('native_validation.tsv',checks)
    summary=[]
    for env in ['nominal','JEFF','ENDF']:
        for role in [0,1,2,3]:
            for channel in ['VetoNu0','VetoNu1','Preshower0']:
                rr=[r for r in coverage if r['environment']==env and r['role']==role and r['channel']==channel]
                summary.append(dict(environment=env,role=role,channel=channel,**{k:sum(r[k] for r in rr) for k in ['parent_N','present','saturated','no_sensitive_hits','inside_MeV','outside_MeV']}))
    table('waveform_coverage.tsv',summary)
    return d


def fit(spec):
    arm,d=spec;tick=time.perf_counter();cpu=time.process_time();x=d['x']
    if arm in ['B','C','D']:x=np.column_stack([x,d['B']])
    if arm in ['C','D']:x=np.column_stack([x,d['C']])
    if arm=='D':x=np.column_stack([x,d['D']])
    train=d['role']==1;cal=d['role']==2;active=d['role']>0;y=np.log(d['truth_E_GeV'])
    w=weights(d['incoming'][train])/d['probability'][train];w/=w.mean()
    dm=xgb.DMatrix(x[train],label=y[train],weight=w);pred=[];roundtrip=0.
    protocol=json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())['baseline']
    for seed in protocol['seeds']:
        params=dict(protocol['xgboost'],seed=seed,base_score=float(np.average(y[train],weights=w)),boost_from_average=0)
        model=xgb.train(params,dm,num_boost_round=protocol['rounds']);path=ART/f'{arm}_{seed}.ubj';model.save_model(path)
        saved=xgb.Booster(params={'nthread':1});saved.load_model(path)
        prediction=model.predict(xgb.DMatrix(x[active])).astype(float);again=saved.predict(xgb.DMatrix(x[active])).astype(float)
        np.testing.assert_array_equal(prediction,again);pred.append(prediction)
    raw=np.full(len(y),np.nan);raw[active]=np.mean(pred,axis=0)
    cw=weights(d['incoming'][cal])/d['probability'][cal];offset=float(np.average(y[cal]-raw[cal],weights=cw))
    prediction=raw+offset;np.savez_compressed(ART/f'{arm}_prediction.npz',raw=raw,cal=prediction)
    return dict(arm=arm,dimensions=x.shape[1],train_N=int(train.sum()),cal_N=int(cal.sum()),offset=offset,CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,roundtrip_prediction_max_abs=roundtrip)


def evaluate(d):
    policies={arm:load(ART/f'{arm}_prediction.npz')['cal'] for arm in ['A','B','C','D']}
    reference=load(ROOT/'ml/artifacts/stage119/response_predictions.npz');index={}
    for j,(env,s,e) in enumerate(zip(reference['environment'],reference['source_index'],reference['input_entry'])):
        if env in ['nominal','JEFF','ENDF']:
            key=(int(s),int(e));assert key not in index;index[key]=j
    ix=np.array([index[(int(s),int(e))] for s,e in zip(d['source_index'],d['input_entry'])])
    np.testing.assert_array_equal(reference['incoming'][ix],d['incoming'])
    policies['direct_cal']=reference['direct_cal'][ix];policies['traditional']=np.log(d['pz']/.8)
    for v in policies.values():v[d['role']==0]=np.nan
    points=[];pairs=[];support=[];power=[];validations=[];gates=[]
    for role in [1,2,3]:
        selected=np.flatnonzero(d['role']==role);sd={k:v[selected] for k,v in d.items()};_,first,gid=np.unique(sd['incoming'],axis=0,return_index=True,return_inverse=True)
        nk=len(first);rng=np.random.default_rng(20261106122+role);draw=np.zeros((500,nk),np.int16)
        for component in sorted(set(sd['component'][first])):
            use=np.flatnonzero(sd['component'][first]==component);draw[:,use]=rng.multinomial(len(use),np.full(len(use),1/len(use)),size=500)
        w=weights(sd['incoming'])/sd['probability'];names=list(policies)
        for layer,mask in masks(sd).items():
            use=selected[mask];ww=w[mask];gg=gid[mask]
            if not len(use):
                support.append(dict(role=role,stratum=layer,N=0,incoming=0));continue
            err=np.column_stack([policies[n][use]-np.log(d['truth_E_GeV'][use]) for n in names]);assert np.isfinite(err).all()
            den=draw@np.bincount(gg,weights=ww,minlength=nk);good=den>0
            agg=np.zeros((nk,len(names)));np.add.at(agg,gg,ww[:,None]*err**2);bt=draw@agg
            base=dict(role=role,stratum=layer,N=len(use),incoming=len(np.unique(gg)),ESS=float(ww.sum()**2/(ww@ww)),valid_draws=int(good.sum()))
            support.append(base)
            for j,name in enumerate(names):
                lo,hi=ci(np.sqrt(bt[good,j]/den[good]));points.append(dict(**base,model=name,**metrics(err[:,j],ww),RMSE_low95=lo,RMSE_high95=hi))
            rel=np.expm1(err);tails={}
            for sign,flag in [('total',abs(rel)>.5),('positive',rel>.5),('negative',rel<-.5)]:
                a=np.zeros_like(agg);np.add.at(a,gg,ww[:,None]*flag);tails[sign]=(a.sum(0)/ww.sum(),draw@a)
            for candidate,ref in [('B','A'),('C','B'),('D','C')]+[(a,b) for a in ['A','B','C','D'] for b in ['direct_cal','traditional']]:
                j,k=names.index(candidate),names.index(ref);ok=good&(bt[:,k]>0);lo,hi=ci(np.sqrt(bt[ok,j]/bt[ok,k]))
                mse_delta=(agg[:,j].sum()-agg[:,k].sum())/ww.sum();dl,dh=ci((bt[ok,j]-bt[ok,k])/den[ok])
                row=dict(**base,candidate=candidate,reference=ref,RMSE_ratio=float(np.sqrt(agg[:,j].sum()/agg[:,k].sum())),low95=lo,high95=hi,MSE_delta=float(mse_delta),MSE_delta_low95=dl,MSE_delta_high95=dh)
                for sign,(central,t) in tails.items():
                    lo,hi=ci(100*(t[ok,j]-t[ok,k])/den[ok]);row.update({sign+'_tail_delta_pp':float(100*(central[j]-central[k])),sign+'_tail_low95_pp':lo,sign+'_tail_high95_pp':hi})
                pairs.append(row)
                if candidate=='B' and ref=='A' and layer in LAYERS and row['low95'] is not None:
                    rw=draw[:,gg]*ww;ind=ci(np.sqrt((rw@err[:,j]**2)/(rw@err[:,k]**2)))
                    delta=max(abs(ind[0]-row['low95']),abs(ind[1]-row['high95']));assert delta<1e-10
                    validations.append(dict(role=role,stratum=layer,paired_interval_max_abs=delta))
                if candidate in ['B','C','D'] and ref in ['A','B','C'] and role==2:
                    contrast=err[:,j]**2-.95**2*err[:,k]**2
                    counts=np.bincount(gg,weights=ww,minlength=nk);has=counts>0
                    values=np.bincount(gg,weights=ww*contrast,minlength=nk)[has]/counts[has]
                    delta=.0975*float(np.average(err[:,k]**2,weights=ww));variance=float(np.var(values,ddof=1)) if len(values)>1 else np.nan
                    needed=int(np.ceil((1.95996398454+.84162123357)**2*variance/delta**2)) if np.isfinite(variance) and delta>0 else None
                    power.append(dict(candidate=candidate,reference=ref,stratum=layer,development_incoming=len(values),target_RMSE_ratio=.95,normal80pct_power_incoming=needed,contrast_variance=variance,reference_MSE=float(np.average(err[:,k]**2,weights=ww)),caveat='conditional pilot normal approximation with variable weights; not guaranteed sufficient N, excludes source/refit/system and all joint gates'))
        for arm in ['A','B','C','D']:
            for layer in LAYERS:
                ref='traditional' if layer in LAYERS[:2] else 'direct_cal';limit=1.05 if ref=='traditional' else 1.01 if layer=='all' else 1.03
                match=next((r for r in pairs if r['role']==role and r['stratum']==layer and r['candidate']==arm and r['reference']==ref),None)
                tail=next((r for r in pairs if r['role']==role and r['stratum']==layer and r['candidate']==arm and r['reference']=='direct_cal'),None)
                gates.append(dict(role=role,arm=arm,stratum=layer,RMSE_upper95=match['high95'] if match else None,limit=limit,RMSE_pass=bool(match and match['high95'] is not None and match['high95']<=limit),tail_pass=bool(tail and all(tail[s+'_tail_high95_pp'] is not None and tail[s+'_tail_high95_pp']<=2 for s in ['total','positive','negative']))))
    table('metrics.tsv',points);table('paired.tsv',pairs);table('support.tsv',support);table('planning_support.tsv',power);table('paired_validation.tsv',validations);table('gates.tsv',gates)
    np.savez_compressed(ART/'predictions.npz',**policies)
    summary=dict(N=len(d['role']),features={k:d[k].shape[1] for k in ['x','B','C','D']},
        reserved_predictions=0,quarantine_predictions=0,roles_preserved=True,
        joint={f'{role}_{a}':all(r['RMSE_pass'] and r['tail_pass'] for r in gates if r['role']==role and r['arm']==a) for role in [2,3] for a in ['A','B','C','D']},
        B_low_increment_supported=all((r['high95'] is not None and r['high95']<1) for r in pairs if r['role']==3 and r['candidate']=='B' and r['reference']=='A' and r['stratum'] in LAYERS[:2]),
        limitations=['developed conditional response cohort','only60 training lowest-bin records;20 development test records','incoming proxies not full GENIE ancestry','source/refit/research-selection/system uncertainty excluded','D covers actual persisted histories, producer termination not certified','not an information bound or independent confirmation'])
    (OUT/'comparison_summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary,flush=True)


def main():
    OUT.mkdir(parents=True,exist_ok=True);ART.mkdir(parents=True,exist_ok=True)
    d=prepare()
    # Exact incoming identities may not cross active roles, including environment views.
    seen={}
    for key,role in zip(map(tuple,d['incoming']),d['role']):
        if role:
            if key in seen:assert seen[key]==role
            seen[key]=role
    with mp.get_context('fork').Pool(4) as pool:fits=pool.map(fit,[(a,d) for a in ['A','B','C','D']])
    (OUT/'fits.json').write_text(json.dumps(fits,indent=2)+'\n')
    evaluate(d)


if __name__=='__main__':main()
