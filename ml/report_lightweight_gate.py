#!/usr/bin/env python3
"""Frozen gate evaluation including nonconvergence, OOF and source-paired costs."""
import json
import numpy as np

from expert_combination import REPO,inputs,subset,masks,LOW,COST,begin,resources,save,route,CELLS
from lightweight_gate import OUT,ART,predict,features
from report_expert_combination import table,metrics,support,boot_weights


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());models=json.loads((OUT/'models.json').read_text())
    d=inputs()
    with np.load(ART/'predictions.npz') as z:a={k:z[k] for k in z.files}
    with np.load(REPO/'ml/artifacts/stage58/predictions.npz') as z:old={k:z[k] for k in z.files}
    b=json.loads((OUT.parent/'stage58_energy_ml/protocol.json').read_text())['timing_medians_pC']
    records=[];paired=[];foldrecords=[];sourcerecords=[];weightrecords=[];cellrecords=[]
    for role in ['cal','eval']:
        dd=subset(d,d['role']==role);sample='cal_OOF' if role=='cal' else 'evaluation';y=np.log(dd['truth_E_GeV']);mm=masks(dd)
        np.testing.assert_array_equal(dd['row'],a[role+'_row']);np.testing.assert_array_equal(dd['row'],old[role+'_row'])
        F=a['cal_oof_F7'] if role=='cal' else a['eval_F7']
        np.testing.assert_array_equal(F,old['cal_oof_F7'] if role=='cal' else old['eval_F7'])
        logs=dict(pz0=np.log(dd['pz']),pz0_over0p8=np.log(dd['pz']/.8),F7=F,
                  four_cell=old['cal_oof_three'] if role=='cal' else old['eval_three'],
                  gate=a['cal_oof_gate'] if role=='cal' else a['eval_gate'])
        weights=np.zeros((len(y),3))
        if role=='cal':
            for f,model in enumerate(models['folds']):
                take=a['cal_fold']==f
                _,weights[take]=predict(subset(dd,take),model,p,True)
        else:_,weights=predict(dd,models['final'],p,True)
        _,active=features(dd);groups,gid,w=boot_weights(dd,p['bootstrap_seed']+(role=='cal'),p['bootstrap_replicates'])
        for name,m in mm.items():
            for model,pred in logs.items():records.append(dict(sample=sample,stratum=name,model=model,**support(dd,m),**metrics(y[m],pred[m])))
            weightrecords.append(dict(sample=sample,stratum=name,**support(dd,m),active_N=int((m&active).sum()),
                mean_w0=float(weights[m,0].mean()) if m.any() else np.nan,
                mean_wmu=float(weights[m,1].mean()) if m.any() else np.nan,
                mean_wF7=float(weights[m,2].mean()) if m.any() else np.nan))
            if not m.any():continue
            for ref in ['pz0_over0p8','F7','four_cell']:
                point=metrics(y[m],logs['gate'][m]);rr=metrics(y[m],logs[ref][m]);ratio=point['log_RMSE']/rr['log_RMSE']
                row=dict(sample=sample,stratum=name,model='gate',reference=ref,**support(dd,m),RMSE_ratio=ratio,gain_pct=100*(1-ratio),
                         RMSE_ratio_low95=np.nan,RMSE_ratio_high95=np.nan,gain_low95_pct=np.nan,gain_high95_pct=np.nan,bootstrap_valid=0)
                ng=len(np.unique(dd['group'][m]));den=w@np.bincount(gid[m],minlength=len(groups))
                if ng>=3:
                    ss=[w@np.bincount(gid[m],weights=(logs[key][m]-y[m])**2,minlength=len(groups)) for key in ['gate',ref]]
                    good=(den>0)&(ss[1]>0);ratios=np.sqrt(ss[0][good]/ss[1][good]);lo,hi=np.quantile(ratios,[.025,.975])
                    row.update(RMSE_ratio_low95=float(lo),RMSE_ratio_high95=float(hi),gain_low95_pct=float(100*(1-hi)),gain_high95_pct=float(100*(1-lo)),bootstrap_valid=int(good.sum()))
                for tail in ['tail50_pct','positive_tail50_pct','negative_tail50_pct','tail100_pct','positive_tail100_pct','negative_tail100_pct']:
                    row[tail+'_delta_pp']=point[tail]-rr[tail];row[tail+'_delta_low95_pp']=np.nan;row[tail+'_delta_high95_pp']=np.nan
                    if ng>=3:
                        threshold=.5 if '50' in tail else 1
                        def indicator(pred):
                            rel=np.expm1(pred[m]-y[m])
                            return rel>threshold if tail.startswith('positive') else rel< -threshold if tail.startswith('negative') else abs(rel)>threshold
                        diff=indicator(logs['gate']).astype(float)-indicator(logs[ref]).astype(float)
                        vals=100*(w@np.bincount(gid[m],weights=diff,minlength=len(groups)))[good]/den[good]
                        lo,hi=np.quantile(vals,[.025,.975]);row[tail+'_delta_low95_pp']=float(lo);row[tail+'_delta_high95_pp']=float(hi)
                paired.append(row)
        for f in (range(3) if role=='cal' else []):
            for name in ['all']+LOW+list(COST)[1:]:
                m=mm[name]&(a['cal_fold']==f)
                for model,pred in logs.items():foldrecords.append(dict(fold=f,stratum=name,model=model,**support(dd,m),**metrics(y[m],pred[m])))
        for group in groups:
            for name in ['all']+LOW+list(COST)[1:]:
                m=mm[name]&(dd['group']==group)
                for model,pred in logs.items():sourcerecords.append(dict(sample=sample,group=group,stratum=name,model=model,**support(dd,m),**metrics(y[m],pred[m])))
        cell=route(dd['pz'],dd['timing'],b)
        for c in range(-1,4):
            for name in ['all']+LOW+list(COST)[1:]:
                m=(cell==c)&mm[name]
                for model in ['F7','four_cell','gate']:
                    cellrecords.append(dict(sample=sample,cell='default_F7' if c<0 else CELLS[c],stratum=name,model=model,
                                            **support(dd,m),**metrics(y[m],logs[model][m])))
    for file,rows in [('metrics',records),('paired',paired),('cal_oof_folds',foldrecords),('source_metrics',sourcerecords),
                      ('weights',weightrecords),('old_cell_metrics',cellrecords)]:table(OUT/(file+'.tsv'),rows)
    acceptance=[];all_converged=all(m['success'] for m in models['folds']+[models['final']])
    for sample in ['cal_OOF','evaluation']:
        for stratum,limit,ref,criterion in [(s,1.05,'pz0_over0p8','recovery') for s in LOW]+[(s,v,'F7','cost') for s,v in COST.items()]:
            r=next(r for r in paired if r['sample']==sample and r['stratum']==stratum and r['reference']==ref)
            acceptance.append(dict(sample=sample,criterion=criterion,stratum=stratum,reference=ref,limit=limit,
                point_ratio=r['RMSE_ratio'],upper95_ratio=r['RMSE_ratio_high95'],point_pass=bool(r['RMSE_ratio']<=limit),
                interval_pass=bool(r['RMSE_ratio_high95']<=limit),tail50_delta_pp=r['tail50_pct_delta_pp'],
                tail50_upper95_delta_pp=r['tail50_pct_delta_high95_pp'],tail50_interval_pass=bool(r['tail50_pct_delta_high95_pp']<=2),
                all_optimizers_converged=all_converged))
    save(OUT/'acceptance.json',dict(checks=acceptance,all_optimizers_converged=all_converged,
        promotion_allowed=bool(all_converged and all(r['interval_pass'] and r['tail50_interval_pass'] for r in acceptance))))
    diagnostics=[]
    for model in models['folds']+[models['final']]:
        selected=[h['iteration'] for h in model['history'] if abs(h['max_low_ratio']-model['max_low_MSE_ratio'])<1e-10]
        last=model['history'][-1]
        diagnostics.append(dict(fold=model['held_fold'],optimizer_status=model['optimizer_status'],
            optimizer_message=model['optimizer_message'],callback_iterations=model['iterations'],
            selected_callback_iteration=selected[0] if selected else 0,
            selected_max_low_MSE_ratio=model['max_low_MSE_ratio'],selected_violation=model['maximum_constraint_violation'],
            rho=model['rho'],parameters_at_bounds=sum(abs(v)>=8-1e-6 for v in model['parameters'][:58]),
            last_callback_low_MSE_ratio=last['max_low_ratio'],last_callback_max_violation=last['maximum_violation'],
            last_callback_is_saved_model=bool(selected and selected[0]==last['iteration']),terminal_parameters_saved=False))
    save(OUT/'optimizer_diagnostics.json',diagnostics)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    def figure(fig,name):
        path=OUT/(name+'.svg');fig.savefig(path);fig.savefig(OUT/(name+'.png'),dpi=135);plt.close(fig)
        path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    edges=[50,75,100,150,200,400,800,1600,3200,6400]
    for name,label in [('pz0_over0p8','pz0 / 0.8'),('F7','F7'),('four_cell','Frozen four-cell mixture'),('gate','Gate: feasible, unconverged')]:
        rr=[next(r for r in records if r['sample']=='evaluation' and r['model']==name and r['stratum']==f'E{lo}_{hi}') for lo,hi in zip(edges[:-1],edges[1:])]
        for ax,key in zip(axes,['log_RMSE','mean_bias_pct']):ax.plot(np.sqrt(np.array(edges[:-1])*edges[1:]),[r[key] for r in rr],'o-',label=label,ms=3)
    for ax in axes:ax.set_xscale('log');ax.set_xlabel('True neutrino energy [GeV]');ax.grid(alpha=.2);ax.axvspan(50,100,color='grey',alpha=.1)
    axes[0].set_ylabel('log-RMSE');axes[1].set_ylabel('Mean relative bias [%]');axes[0].legend(fontsize=8);axes[1].axhline(0,color='black',lw=.6)
    fig.suptitle('Fixed 8-unit gate: nominal development evaluation\nAll 4 optimizers hit iteration limit; feasible checkpoints only, no promotion')
    figure(fig,'gate_response')
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for f,m in enumerate(models['folds']+[models['final']]):
        h=m['history'];xx=[r['iteration'] for r in h]
        axes[0].plot(xx,[r['max_low_ratio'] for r in h],label='final' if f==3 else 'fold '+str(f))
        axes[1].semilogy(xx,np.maximum(1e-14,[r['maximum_violation'] for r in h]))
    axes[0].set_ylabel('Worst low-energy MSE ratio (training)');axes[0].legend(fontsize=8)
    axes[1].set_ylabel('Max violation (including epigraph)');axes[1].axhline(p['feasibility_tolerance'],color='red',ls='--')
    for ax in axes:ax.set_xlabel('Optimizer callback iteration');ax.grid(alpha=.2)
    fig.suptitle('Predefined single-start optimization: no retry or budget extension\nTrace values may violate constraints; deployed checkpoint must be feasible')
    figure(fig,'gate_optimization')
    save(OUT/'report_resources.json',dict(**resources(start),bootstrap_replicates=500,additional_fit_calls=0,
        intervals='fixed predictions, source stratified; exclude optimizer/refit/calibration/response/research selection uncertainty',
        promotion_allowed=False if not all_converged else all(r['interval_pass'] for r in acceptance)))
    print(json.dumps(acceptance,indent=2))


if __name__=='__main__':main()
