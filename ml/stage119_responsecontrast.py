"""Common incoming-cluster environment contrasts and linked GENIE failures."""
import json

import numpy as np

from stage119_curve_common import ROOT,OUT,CACHE,masks,weights,load,table
from stage119_reportcurve import ci
from stage119_response import read


def contrasts(d):
    e,y,z=d['truth_E_GeV'],d['y_lepton'],d['vertex_z_mm'];rows=[];checks=[]
    cells=np.array([f'{c}:E{np.searchsorted([100,200,400,1000],ee,side="right")}:y{np.searchsorted([.2,.5,.8],v,side="right") if np.isfinite(v) and 0<=v<1 else 4}:z{np.searchsorted([-2200,-1950],zz,side="right")}' for c,ee,v,zz in zip(d['component'],e,y,z)])
    rng=np.random.default_rng(20261105199)
    for envs in [('nominal','JEFF','ENDF'),('Standard','NUX')]:
        support={env:set(cells[d['environment']==env]) for env in envs};common=set.intersection(*support.values());base=np.zeros(len(e));mass={}
        allix=np.flatnonzero(np.isin(d['environment'],envs));keys,first,gid=np.unique(d['incoming'][allix],axis=0,return_index=True,return_inverse=True)
        globalgid=np.full(len(e),-1);globalgid[allix]=gid;nk=len(keys);draw=np.zeros((500,nk),np.int16)
        for c in sorted(set(d['component'][allix][first])):
            ix=np.flatnonzero(d['component'][allix][first]==c);draw[:,ix]=rng.multinomial(len(ix),np.full(len(ix),1/len(ix)),size=500)
        for env in envs:
            ix=np.flatnonzero(d['environment']==env);w=weights(d['incoming'][ix])/d['probability'][ix];base[ix]=w
            mass[env]={c:float(w[cells[ix]==c].sum()) for c in support[env]}
        target={c:min(mass[env][c]/sum(mass[env].values()) for env in envs) for c in common}
        pairs=[('JEFF','nominal'),('ENDF','nominal'),('ENDF','JEFF')] if len(envs)==3 else [('NUX','Standard')]
        for scheme in ['sampled_population','common_E_y_z_component']:
            data={}
            for env in envs:
                ix=np.flatnonzero((d['environment']==env)&(np.isin(cells,list(common)) if scheme!='sampled_population' else True));w=base[ix].copy()
                if scheme!='sampled_population':w*=np.array([target[c]/mass[env][c] for c in cells[ix]])
                for layer,mask in masks({k:v[ix] for k,v in d.items()}).items():
                    if not mask.any():continue
                    use=ix[mask];ww=w[mask];gg=globalgid[use];den=draw@np.bincount(gg,weights=ww,minlength=nk)
                    for policy in ['direct_cal','traditional']:
                        error=d[policy][use]-np.log(e[use]);loss=np.bincount(gg,weights=ww*error**2,minlength=nk);bt=draw@loss
                        rel=np.expm1(error);tails={}
                        for sign,flag in [('total',abs(rel)>.5),('positive',rel>.5),('negative',rel<-.5)]:
                            tails[sign]=(float(np.average(flag,weights=ww)),draw@np.bincount(gg,weights=ww*flag,minlength=nk))
                        data[(env,layer,policy)]=dict(N=len(use),incoming=len(np.unique(gg)),RMSE=float(np.sqrt(np.average(error**2,weights=ww))),
                            den=den,loss=bt,tails=tails)
                        # Separate row-space check on the core strata, avoiding
                        # inference about sparse unsupported bootstrap draws.
                        if layer in ['all','E50_100','E100_200']:
                            sw=draw[:,gg]*ww;ind=sw@error**2
                            delta=float(np.max(abs(ind-bt)));assert delta<1e-8
                            checks.append(dict(environment=env,scheme=scheme,stratum=layer,policy=policy,row_cluster_loss_max_abs=delta))
            for a,b in pairs:
                for layer in masks(d):
                    for policy in ['direct_cal','traditional']:
                        if (a,layer,policy) not in data or (b,layer,policy) not in data:continue
                        left,right=data[(a,layer,policy)],data[(b,layer,policy)];valid=(left['den']>0)&(right['den']>0)&(right['loss']>0)
                        ratio=np.sqrt((left['loss'][valid]/left['den'][valid])/(right['loss'][valid]/right['den'][valid]));lo,hi=ci(ratio)
                        row=dict(environment=a,reference=b,scheme=scheme,stratum=layer,policy=policy,N=left['N'],reference_N=right['N'],
                            RMSE_ratio=left['RMSE']/right['RMSE'],low95=lo,high95=hi,valid_draws=int(valid.sum()))
                        for sign in ['total','positive','negative']:
                            ac,at=left['tails'][sign];bc,bt=right['tails'][sign];lo,hi=ci(100*(at[valid]/left['den'][valid]-bt[valid]/right['den'][valid]))
                            row.update({sign+'_tail_delta_pp':100*(ac-bc),sign+'_tail_low95_pp':lo,sign+'_tail_high95_pp':hi})
                        rows.append(row)
    table('response_environment_contrasts.tsv',rows);table('response_contrast_validation.tsv',checks)


def genie_failures(d):
    labels=load('ntuples/energy_ml_stage119/genie_labels.npz');lookup={(int(s),int(e)):i for i,(s,e) in enumerate(zip(labels['source_index'],labels['input_entry']))}
    rows=[];coverage=[];scope=np.isin(d['environment'],['Standard','NUX']);W=np.full(len(scope),np.nan);Q2=W.copy();pre=W.copy();post=W.copy();linked=np.zeros(len(scope),bool)
    for j in np.flatnonzero(scope):
        i=lookup[(int(d['source_index'][j]),int(d['input_entry'][j]))]
        assert labels['eventID'][i]==d['eventID'][j] and labels['run'][i]==d['run'][j]
        linked[j]=labels['linked'][i]
        if linked[j]:W[j]=labels['W'][i];Q2[j]=labels['Q2'][i];pre[j]=labels['pre_neutron'][i];post[j]=labels['post_neutron'][i]
    direct=abs(np.expm1(d['direct_cal']-np.log(d['truth_E_GeV'])))>.5;trad=abs(np.expm1(d['traditional']-np.log(d['truth_E_GeV'])))>.5
    groups=dict(all=np.ones(len(scope),bool),direct_tail50=direct,direct_pass50=~direct,direct_fail_trad_pass=direct&~trad,trad_fail_direct_pass=trad&~direct)
    for env in ['Standard','NUX']:
        for layer,mask in masks(d).items():
            use=scope&(d['environment']==env)&mask
            coverage.append(dict(environment=env,stratum=layer,selected_N=int(use.sum()),linked_N=int((use&linked).sum()),W_known_N=int((use&np.isfinite(W)).sum())))
            for group,g in groups.items():
                selected=use&g;known=selected&np.isfinite(W);valid=selected&linked
                avg=lambda a:float(np.mean(a[valid])) if valid.any() else None
                rows.append(dict(environment=env,stratum=layer,error_group=group,selected_N=int(selected.sum()),linked_N=int(valid.sum()),W_known_N=int(known.sum()),
                    W_lt2p3_N=int((known&(W<2.3)).sum()),W_2p3_3_N=int((known&(W>=2.3)&(W<3)).sum()),W_ge3_N=int((known&(W>=3)).sum()),
                    W_median_GeV=float(np.median(W[known])) if known.any() else None,Q2_median_GeV2=float(np.median(Q2[valid])) if valid.any() else None,
                    preFSI_neutron_mean=avg(pre),postFSI_neutron_mean=avg(post)))
    table('genie_failure_W_FSI.tsv',rows);table('genie_selected_link_coverage.tsv',coverage)
    (OUT/'genie_failure_scope.json').write_text(json.dumps(dict(selected_N=int(scope.sum()),linked_selected_N=int((scope&linked).sum()),
        W_known_selected_N=int((scope&np.isfinite(W)).sum()),W='struck status11 nucleon + nu - primary charged mu, original generator GeV four-vectors',
        classification='W range proxy for AGKY/PYTHIA transition only; generic interaction/channel/FSI causal effect not certified',
        link='exact incoming and vertex after documented p6 float persistence, primary y closure; eventID alone never sufficient',
        interpretation='descriptive fixed-model failure composition; not an intervention or an oracle/energy feature'),indent=2)+'\n')


def main():
    parts=[]
    for name,prefix in [('production_contract.json','production'),('pythia_production_contract.json','pythia_production')]:
        d,_,_=read(json.loads((OUT/name).read_text()),prefix);parts.append(d)
    common=set.intersection(*(set(p) for p in parts));d={k:np.concatenate([p[k] for p in parts]) for k in common}
    pred=load('ml/artifacts/stage119/response_predictions.npz')
    for k in ['incoming','source_index','environment','input_entry','truth_E_GeV','pz']:np.testing.assert_array_equal(d[k],pred[k])
    for k in ['direct_cal','traditional']:d[k]=pred[k]
    contrasts(d);genie_failures(d)
    print('Fixed predictions exact, environment contrasts and linked failures complete',flush=True)


if __name__=='__main__':main()
