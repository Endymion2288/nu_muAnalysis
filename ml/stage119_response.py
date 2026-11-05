"""Fixed direct/traditional transport and hadronization response comparisons."""
import json
import tarfile

import numpy as np
import xgboost as xgb

from audited_features import configuration
from stage119_curve_common import ROOT,OUT,CACHE,LAYERS,masks,table,weights
from stage119_reportcurve import metrics,ci


def read(contract,prefix):
    parts=[];parent_rows=[];cost=[]
    for i,r in enumerate(contract['requests']):
        with tarfile.open(CACHE/f'{prefix}_{i}.tar.gz') as t:
            assert t.extractfile('result/exitcode.txt').read().strip()==b'0'
            with np.load(t.extractfile('result/selected.npz')) as z:a={k:z[k] for k in z.files if k!='metadata_json'}
            selected_entries=set(map(int,a['input_entry']))
            for member in t.getnames():
                if member.endswith('_time.txt'):
                    text=t.extractfile(member).read().decode();value={}
                    for line in text.splitlines():
                        if 'User time (seconds):' in line:value['user_s']=float(line.split(':')[-1])
                        if 'System time (seconds):' in line:value['system_s']=float(line.split(':')[-1])
                        if 'Maximum resident set size (kbytes):' in line:value['RSS_KiB']=int(line.split(':')[-1])
                        if 'Elapsed (wall clock)' in line:
                            h=list(map(float,line.split('): ')[-1].split(':')));value['wall_s']=sum(v*60**j for j,v in enumerate(h[::-1]))
                    cost.append(dict(index=i,run=r['source']['run'],step=member,**value))
        s=r['source'];kind=s['kind']
        if prefix=='production':
            if kind=='expansion':continue
            env='nominal' if kind=='nominal' else 'JEFF' if 200110<=s['run']<=200112 else 'ENDF'
            with np.load(CACHE/f'pilot_{i}.npz') as z:parent={k:z[k] for k in ['E','y','vertex_z','incoming','eventID']}
        else:
            env=s['environment'];p=json.loads((OUT/f'pythia_parent_{i}.json').read_text())['parents']
            parent=dict(E=np.array([v.get('E_GeV',np.nan) for v in p]),y=np.array([v.get('y',np.nan) for v in p]),
                vertex_z=np.array([v.get('vertex_mm',[np.nan]*3)[2] for v in p]),incoming=np.array([v.get('incoming',[np.nan]*4) for v in p]),eventID=np.array([v['eventID'] for v in p]))
        a['pz']=a['reco_pz_GeV'];n=len(a['run']);a.update(environment=np.full(n,env),component=np.full(n,s['component']),source_index=np.full(n,i),
            probability=np.full(n,s.get('file_inclusion_probability',s.get('file_probability',1))))
        parts.append(a)
        for name,mask in dict(all=np.ones(r['parent_N'],bool),E50_100=(parent['E']>=50)&(parent['E']<100),E100_200=(parent['E']>=100)&(parent['E']<200),high_y=parent['y']>=.8,highE=parent['E']>=1000).items():
            selected=np.array([j in selected_entries for j in range(r['parent_N'])])
            parent_rows.append(dict(environment=env,index=i,run=s['run'],component=s['component'],stratum=name,parent_N=int(mask.sum()),selected_N=int((selected&mask).sum()),file_probability=s.get('file_inclusion_probability',s.get('file_probability',1))))
    return {k:np.concatenate([p[k] for p in parts]) for k in parts[0]},parent_rows,cost


def evaluate(d):
    names=configuration()['features'];pred=[]
    protocol=json.loads((OUT.parent/'stage87_energy_ml/protocol.json').read_text())
    for seed in protocol['baseline']['seeds']:
        m=xgb.Booster(params={'nthread':1});m.load_model(ROOT/f'ml/artifacts/stage87/direct_{seed}.ubj');assert m.feature_names==names
        pred.append(m.predict(xgb.DMatrix(d['x'],feature_names=names)).astype(float))
    with np.load(ROOT/'ml/artifacts/stage87/predictions.npz') as z:offset=float((z['direct_cal']-z['direct_raw'])[0])
    d['direct_cal']=np.mean(pred,axis=0)+offset;d['traditional']=np.log(d['pz']/.8)
    return d


def summarize(d):
    points=[];paired=[];coverage=[];rng=np.random.default_rng(20261105196)
    # No common-support bin or balance target is selected using model outcomes.
    E=d['truth_E_GeV'];y=d['y_lepton'];z=d['vertex_z_mm']
    cells=np.array([f'{c}:E{np.searchsorted([100,200,400,1000],e,side="right")}:y{np.searchsorted([.2,.5,.8],v,side="right") if np.isfinite(v) and 0<=v<1 else 4}:z{np.searchsorted([-2200,-1950],zz,side="right")}' for c,e,v,zz in zip(d['component'],E,y,z)])
    for envs in [('nominal','JEFF','ENDF'),('Standard','NUX')]:
        support={env:set(cells[d['environment']==env]) for env in envs};common=set.intersection(*support.values())
        # Source-sampling weights and common-cell overlap target, independently
        # normalized in each environment; no GENIE family pairing is implied.
        base=np.zeros(len(E));mass={}
        for env in envs:
            ix=np.flatnonzero(d['environment']==env);w=weights(d['incoming'][ix])/d['probability'][ix];base[ix]=w
            mass[env]={c:float(w[cells[ix]==c].sum()) for c in support[env]}
        target={c:min(mass[env][c]/sum(mass[env].values()) for env in envs) for c in common}
        for env in envs:
            for scheme in ['sampled_population','common_E_y_z_component']:
                ix=np.flatnonzero((d['environment']==env)&(np.isin(cells,list(common)) if scheme!='sampled_population' else True))
                w=base[ix].copy()
                if scheme!='sampled_population':w*=np.array([target[c]/mass[env][c] for c in cells[ix]])
                if not len(ix):continue
                _,gid,count=np.unique(d['incoming'][ix],axis=0,return_inverse=True,return_counts=True);nk=len(count)
                draw=rng.multinomial(nk,np.full(nk,1/nk),size=500)
                sd={k:v[ix] for k,v in d.items()};coverage.append(dict(environment=env,scheme=scheme,N=len(ix),incoming=nk,common_cells=len(common),
                    retained_sample_weight=float(base[ix].sum()/base[d['environment']==env].sum()),overlap_mass=sum(target.values())))
                for layer,mask in masks(sd).items():
                    if not mask.any():continue
                    use=ix[mask];ww=w[mask];gg=gid[mask];den=draw@np.bincount(gg,weights=ww,minlength=nk);valid=den>0
                    ytruth=np.log(E[use]);bt={};tails={}
                    for policy in ['traditional','direct_cal']:
                        err=d[policy][use]-ytruth;loss=np.bincount(gg,weights=ww*err**2,minlength=nk);bt[policy]=draw@loss
                        lo,hi=ci(np.sqrt(bt[policy][valid]/den[valid]))
                        points.append(dict(environment=env,scheme=scheme,stratum=layer,policy=policy,N=len(use),incoming=len(np.unique(gg)),
                            ESS=float(ww.sum()**2/(ww@ww)),**metrics(err,ww),RMSE_low95=lo,RMSE_high95=hi))
                        rel=np.expm1(err);tails[policy]={}
                        for sign,flag in [('total',abs(rel)>.5),('positive',rel>.5),('negative',rel<-.5)]:
                            tails[policy][sign]=(float(np.average(flag,weights=ww)),draw@np.bincount(gg,weights=ww*flag,minlength=nk))
                    good=valid&(bt['traditional']>0);lo,hi=ci(np.sqrt(bt['direct_cal'][good]/bt['traditional'][good]))
                    a,b=[next(r for r in points[::-1] if r['environment']==env and r['scheme']==scheme and r['stratum']==layer and r['policy']==p) for p in ['direct_cal','traditional']]
                    row=dict(environment=env,scheme=scheme,stratum=layer,N=len(use),direct_over_traditional=a['log_RMSE']/b['log_RMSE'],low95=lo,high95=hi)
                    for sign in ['total','positive','negative']:
                        a,at=tails['direct_cal'][sign];b,btail=tails['traditional'][sign];lo,hi=ci(100*(at[good]-btail[good])/den[good])
                        row.update({sign+'_tail_delta_pp':100*(a-b),sign+'_tail_low95_pp':lo,sign+'_tail_high95_pp':hi})
                    paired.append(row)
    table('response_metrics.tsv',points);table('response_direct_traditional.tsv',paired);table('response_common_support.tsv',coverage)


def transport_pairs(d):
    # Parent match certification is limited to documented EVNT plus exact
    # incoming, vertex and primary state; no full-record or seed equivalence.
    p=json.loads((OUT/'production_contract.json').read_text());datasets={}
    for i,r in enumerate(p['requests']):
        if r['source']['kind']=='expansion':continue
        with np.load(CACHE/f'pilot_{i}.npz') as z:
            a={k:z[k] for k in ['incoming','vertex_z','vertex_r','Emu','primary_valid','E','y','input_entry']}
        env='nominal' if r['source']['kind']=='nominal' else 'JEFF' if r['source']['run']<=200112 else 'ENDF'
        selected={int(e):j for j,e in enumerate(d['input_entry']) if d['source_index'][j]==i and d['environment'][j]==env}
        for j in range(len(a['E'])):
            if not a['primary_valid'][j]:continue
            key=(r['source']['component'],*a['incoming'][j],float(a['vertex_z'][j]),float(a['vertex_r'][j]),float(a['Emu'][j]))
            datasets.setdefault(env,{}).setdefault(key,[]).append((i,j,selected.get(j)))
    rows=[];migration=[];rng=np.random.default_rng(20261105197)
    for left,right in [('nominal','JEFF'),('nominal','ENDF'),('JEFF','ENDF')]:
        common=set(datasets[left])&set(datasets[right]);pairs=[];both=0;leftonly=0;rightonly=0;neither=0;ambiguous=0
        for key in common:
            a,b=datasets[left][key],datasets[right][key]
            if len(a)!=1 or len(b)!=1:ambiguous+=1;continue
            ia,ib=a[0][2],b[0][2]
            if ia is not None and ib is not None:pairs.append((ia,ib));both+=1
            elif ia is not None:leftonly+=1
            elif ib is not None:rightonly+=1
            else:neither+=1
        migration.append(dict(left=left,right=right,matched_parent_states=len(common),ambiguous_states=ambiguous,both_selected=both,left_only_selected=leftonly,right_only_selected=rightonly,neither_selected=neither,
            certification='same documented component EVNT and exact incoming/z/r/primary-E, full final state and source-entry genealogy not certified; conditional matched states only'))
        if not pairs:continue
        aa,bb=np.array(pairs).T
        for layer,mask in masks({k:v[aa] for k,v in d.items()}).items():
            if not mask.any():continue
            a,b=aa[mask],bb[mask];E=d['truth_E_GeV'][a]
            for policy in ['traditional','direct_cal']:
                error_a=d[policy][a]-np.log(E);error_b=d[policy][b]-np.log(d['truth_E_GeV'][b]);delta=error_b**2-error_a**2
                boots=np.array([delta[rng.integers(0,len(delta),len(delta))].mean() for _ in range(500)])
                lo,hi=ci(boots);rows.append(dict(left=left,right=right,stratum=layer,policy=policy,N=len(a),left_log_RMSE=float(np.sqrt(np.mean(error_a**2))),
                    right_log_RMSE=float(np.sqrt(np.mean(error_b**2))),MSE_delta=float(delta.mean()),delta_low95=lo,delta_high95=hi))
    table('response_parent_migration.tsv',migration);table('response_matched_transport.tsv',rows)


def main():
    parts=[];parents=[];cost=[]
    for name,prefix in [('production_contract.json','production'),('pythia_production_contract.json','pythia_production')]:
        d,a,c=read(json.loads((OUT/name).read_text()),prefix);parts.append(d);parents+=a;cost+=c
    # Extractors have the same schema; only shared scientific fields needed.
    common=set.intersection(*(set(p) for p in parts));d={k:np.concatenate([p[k] for p in parts]) for k in sorted(common)}
    d=evaluate(d);np.savez_compressed(ROOT/'ml/artifacts/stage119/response_predictions.npz',**{k:d[k] for k in ['incoming','source_index','environment','input_entry','truth_E_GeV','pz','direct_cal','traditional']})
    table('response_parent_support.tsv',parents);table('production_cost.tsv',cost);summarize(d);transport_pairs(d)
    (OUT/'response_summary.json').write_text(json.dumps(dict(environments={e:int((d['environment']==e).sum()) for e in np.unique(d['environment'])},
        frozen_models=True,energy_fits=0,held_environment='HERMES not inferred',matching='conditional E/y/z/component overlap, not randomized or certified full GENIE-family pairing',
        calibration='same d32 reconstruction and one measured payload conversion03->01; original HITS/digitization producer differences remain explicit'),indent=2)+'\n')


if __name__=='__main__':main()
