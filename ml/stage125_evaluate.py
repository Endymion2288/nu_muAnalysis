"""Frozen direct62 transport assessment; no fitting, retuning or recalibration."""
import csv
import io
import json
import os
import resource
import tarfile
import time
from pathlib import Path

import numpy as np
import xgboost as xgb
from audited_features import configuration

ROOT=Path(__file__).resolve().parents[1]
INPUT=Path(os.environ.get('NU_MU_STAGE125_INPUT_ROOT',str(ROOT)))
OUT=ROOT/'workbook/stage125_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage125'
TUNES=['FTF_BIC','FTFP_INCLXX','JEFF33','ENDFB8','QGSP_BERT']
EDGES=np.array([0,50,100,200,300,400,600,800,1000,1600,3200,6400,np.inf])
PAPER=np.array([0,100,300,600,1000,np.inf])


def table(name,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=keys,delimiter='\t',lineterminator='\n',restval='NA');w.writeheader();w.writerows(rows)


def load(path):
    with np.load(path) as z:return {k:z[k] for k in z.files}


def quantile(x,w,q):
    order=np.argsort(x,kind='stable');x=x[order];w=w[order]
    return np.interp(q,(np.cumsum(w)-.5*w)/w.sum(),x)


def metrics(error,w):
    q=quantile(np.expm1(error),w,[.16,.5,.84]);den=w.sum()
    return dict(log_RMSE=float(np.sqrt(np.dot(w,error**2)/den)),mean_log_bias=float(np.dot(w,error)/den),
                median_bias_pct=float(100*q[1]),R68_pct=float(50*(q[2]-q[0])),
                q16_pct=float(100*q[0]),q84_pct=float(100*q[2]),
                tail50_pct=float(100*np.dot(w,abs(np.expm1(error))>.5)/den),
                positive_tail50_pct=float(100*np.dot(w,np.expm1(error)>.5)/den),
                negative_tail50_pct=float(100*np.dot(w,np.expm1(error)<-.5)/den))


def predict(x,plan):
    names=configuration()['features'];matrix=xgb.DMatrix(x,feature_names=names,nthread=4)
    pp=[]
    for seed in plan['seeds']:
        model=xgb.Booster(params={'nthread':4});model.load_model(INPUT/f'ml/artifacts/stage87/direct_{seed}.ubj')
        assert model.feature_names==names and model.num_boosted_rounds()==400
        pp.append(model.predict(matrix).astype(float))
    return np.mean(pp,axis=0)


def collect(plan):
    parts=[];rows=[]
    for s in plan['sources']:
        path=INPUT/f'ntuples/energy_ml_stage125/production_{s["index"]}.tar.gz'
        if not path.exists() and os.environ.get('NU_MU_STAGE125_PREVIEW')=='1':continue
        with tarfile.open(path) as t:
            get=lambda n:t.extractfile('result/'+n).read()
            assert int(get('exitcode.txt'))==0,(s['index'],'failed source')
            parent=json.loads(get('request_summary.json'));names=t.getnames()
            row=dict(index=s['index'],run=s['run'],tune=s['tune'],component=s['component'],
                     parent_N=parent['parent_N'],file_probability=s['file_probability'],selected_N=0)
            if 'result/selected.npz' in names:
                z=load(io.BytesIO(get('selected.npz')));md=json.loads(str(z['metadata_json']));n=len(z['x'])
                assert z['x'].shape==(n,62) and md['parent_identity']['exact_run_event_incoming']
                row['selected_N']=n
                row['superset_N']=md['raw_N']
                for key,value in zip(md['cutflow_names'],md['cutflow_passed']):row['cut_'+key]=value
                a={k:z[k] for k in ['x','incoming','truth_E_GeV','reco_pz_GeV','run','eventID','input_entry','y_lepton','primary_valid','confirmed','vertex_z_mm']}
                a.update(source=np.full(n,s['index']),tune=np.full(n,s['tune']),component=np.full(n,s['component']),
                         probability=np.full(n,s['file_probability']))
                parts.append(a)
            rows.append(row)
    table('source_support.tsv',rows)
    d={k:np.concatenate([a[k] for a in parts]) for k in parts[0]}
    return d,rows


def main():
    start=time.perf_counter();cpu=time.process_time();OUT.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
    plan=json.loads((INPUT/'workbook/stage125_energy_ml/protocol.json').read_text())
    d,support=collect(plan);old=load(INPUT/'ntuples/energy_ml_stage119/old_input.npz')
    saved=load(INPUT/'ml/artifacts/stage87/predictions.npz');ix=saved['row']
    inference_start=time.perf_counter();raw=predict(old['x'][ix],plan);reference_inference_wall_s=time.perf_counter()-inference_start
    np.testing.assert_array_equal(raw,saved['direct_raw'])
    np.testing.assert_array_equal(raw+plan['offset_log'],saved['direct_cal'])
    ref=old['role'][ix]==3
    reference=metrics(saved['direct_cal'][ref]-np.log(old['truth_E_GeV'][ix][ref]),old['weight'][ix][ref])
    assert abs(reference['log_RMSE']-.287491)<1e-6
    reference_data=dict(truth_E_GeV=old['truth_E_GeV'][ix][ref],direct_logE=saved['direct_cal'][ref],
                        traditional_logE=np.log(old['pz'][ix][ref]/.8),weight=old['weight'][ix][ref])
    reference_rows=[]
    for layer,mask in [('all',np.ones(int(ref.sum()),bool))]+[(f'E{lo:g}_{hi:g}',(reference_data['truth_E_GeV']>=lo)&(reference_data['truth_E_GeV']<hi)) for lo,hi in zip(EDGES[:-1],EDGES[1:])]:
        if not mask.any():continue
        for model in ['direct','traditional']:
            error=reference_data[model+'_logE'][mask]-np.log(reference_data['truth_E_GeV'][mask])
            reference_rows.append(dict(stratum=layer,model=model,N=int(mask.sum()),**metrics(error,reference_data['weight'][mask])))
    table('stage87_reference_metrics.tsv',reference_rows)
    # Exact native-MeV identity is a proxy, not an assertion of full lineage.
    keys,inverse=np.unique(d['incoming'],axis=0,return_inverse=True);d['key_id']=inverse
    traincal=set(map(tuple,old['incoming'][np.isin(old['role'],[1,2])]))
    known_test=set(map(tuple,old['incoming'][old['role']==3]))
    d['fit_overlap']=np.array([tuple(k) in traincal for k in d['incoming']])
    d['test_overlap']=np.array([tuple(k) in known_test for k in d['incoming']])
    inference_start=time.perf_counter();d['direct_logE']=predict(d['x'],plan)+plan['offset_log']
    new_inference_wall_s=time.perf_counter()-inference_start
    d['traditional_logE']=np.log(d['reco_pz_GeV']/.8)
    assert np.isfinite(d['direct_logE']).all() and np.isfinite(d['traditional_logE']).all()
    d['energy_bin']=np.searchsorted(EDGES,d['truth_E_GeV'],side='right')-1
    d['component_code']=np.searchsorted(np.array(['charm','k','pi']),d['component'])
    d['weight']=np.zeros(len(inverse))
    for tune in TUNES:
        m=d['tune']==tune;count=np.bincount(inverse[m],minlength=len(keys))
        d['weight'][m]=1/count[inverse[m]]/d['probability'][m]
    # Primary uses no known train/cal incoming, including across response tunes.
    primary=~d['fit_overlap'];d['primary']=primary
    # Count source components linked by the exact incoming proxy. This makes
    # clear why file counts cannot be interpreted as independent generators.
    parent=np.arange(len(plan['sources']));first={}
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for source,key in zip(d['source'],inverse):
        source,key=int(source),int(key)
        if key in first:
            a,b=root(source),root(first[key]);parent[max(a,b)]=min(a,b)
        else:first[key]=source
    graph=[]
    for c in ['pi','k','charm']:
        ss=np.unique(d['source'][d['component']==c]);roots=[root(int(s)) for s in ss]
        graph.append(dict(component=c,selected_sources=len(ss),incoming_linked_source_components=len(set(roots))))
    table('source_dependence.tsv',graph)
    profiles=[];train=old['role']==1;features=configuration()['features']
    for j,name in enumerate(features):
        a=old['x'][train,j];w=old['weight'][train];valid=np.isfinite(a)
        trainq=quantile(a[valid],w[valid],[.16,.5,.84]);trainmin,trainmax=np.min(a[valid]),np.max(a[valid])
        for t in TUNES:
            m=(d['tune']==t)&primary;x=d['x'][m,j];ww=d['weight'][m];finite=np.isfinite(x)
            q=quantile(x[finite],ww[finite],[.16,.5,.84]) if finite.any() else [np.nan]*3
            profiles.append(dict(tune=t,feature=name,N=int(m.sum()),missing_pct=100*np.dot(ww,~finite)/ww.sum(),
                                 q16=q[0],median=q[1],q84=q[2],train_q16=trainq[0],train_median=trainq[1],train_q84=trainq[2],
                                 median_shift_over_train_R68=(q[1]-trainq[1])/((trainq[2]-trainq[0])/2) if trainq[2]>trainq[0] else np.nan,
                                 outside_train_minmax_pct=100*np.dot(ww,finite&((x<trainmin)|(x>trainmax)))/ww.sum()))
    table('feature_profiles.tsv',profiles)
    allrows=[];matrices=[];selection=[];intersections=[];summaries=[]
    for s in plan['inventory']:
        rr=[r for r in support if r['run']==s['run']];parent=sum(r['parent_N'] for r in rr);selected=sum(r['selected_N'] for r in rr)
        fiducial=sum(r.get('cut_Truth pz > 50 GeV',0) for r in rr)
        selection.append(dict(run=s['run'],tune=s['tune'],component=s['component'],parent_N=parent,selected_N=selected,
                              selected_fraction=selected/parent,files=len(rr),file_probability=s['file_probability'],
                              fiducial_CC_numu_pz50_N=fiducial,
                              fiducial_selection_efficiency=selected/fiducial if fiducial else np.nan,
                              scope='unweighted production-view efficiency; denominator original truth CC/numu/fiducial/r<100/pz>50; no model selection'))
    table('selection_yields.tsv',selection)
    # Fixed fine truth-energy x component standardization. Target = minimum
    # normalized mass across tunes, normalized on common support only.
    cell=d['energy_bin']*3+d['component_code'];nc=len(EDGES)*3
    masses=np.array([np.bincount(cell[(d['tune']==t)&primary],weights=d['weight'][(d['tune']==t)&primary],minlength=nc) for t in TUNES])
    fraction=masses/masses.sum(1)[:,None];target=fraction.min(0);overlap=float(target.sum());target/=target.sum()
    d['standard_weight']=np.zeros(len(inverse))
    for j,t in enumerate(TUNES):
        m=(d['tune']==t)&primary;den=masses[j,cell[m]]
        d['standard_weight'][m]=d['weight'][m]*target[cell[m]]/den
        summaries.append(dict(tune=t,selected_N=int((d['tune']==t).sum()),primary_N=int(m.sum()),
                              primary_unique_incoming=len(np.unique(inverse[m])),
                              fit_overlap_N=int(((d['tune']==t)&d['fit_overlap']).sum()),
                              known_test_overlap_N=int((m&d['test_overlap']).sum()),
                              inverse_probability_weight_sum=float(d['weight'][m].sum()),
                              standardized_ESS=float(d['standard_weight'][m].sum()**2/np.dot(d['standard_weight'][m],d['standard_weight'][m]))))
    for j,t in enumerate(TUNES):
        for c in range(nc):
            intersections.append(dict(tune=t,cell=c,mass=float(fraction[j,c]),common_target=float(target[c]),overlap_mass=overlap))
    table('sample_summary.tsv',summaries);table('common_support.tsv',intersections)
    # Secondary selection-composition control frozen before any new forward:
    # same E/component cells, plus original Stage119 y/depth boundaries.
    ybin=np.searchsorted([.2,.5,.8],d['y_lepton'],side='right');ybin[~np.isfinite(d['y_lepton'])|~d['primary_valid']]=4
    zbin=np.searchsorted([-2200,-1950],d['vertex_z_mm'],side='right');assert np.isfinite(d['vertex_z_mm']).all()
    fullcell=(cell*5+ybin)*3+zbin;nfull=nc*15
    fullmass=np.array([np.bincount(fullcell[(d['tune']==t)&primary],weights=d['weight'][(d['tune']==t)&primary],minlength=nfull) for t in TUNES])
    fullfraction=fullmass/fullmass.sum(1)[:,None];fulltarget=fullfraction.min(0);full_overlap=float(fulltarget.sum());fulltarget/=fulltarget.sum()
    d['matched_weight']=np.zeros(len(inverse));fullrows=[]
    for j,t in enumerate(TUNES):
        m=(d['tune']==t)&primary;d['matched_weight'][m]=d['weight'][m]*fulltarget[fullcell[m]]/fullmass[j,fullcell[m]]
        summaries[j]['matched_ESS']=float(d['matched_weight'][m].sum()**2/np.dot(d['matched_weight'][m],d['matched_weight'][m]))
        summaries[j]['matched_retained_views']=int((m&(d['matched_weight']>0)).sum())
        for c in range(nfull):
            if fullmass[j,c]>0 or fulltarget[c]>0:fullrows.append(dict(tune=t,cell=c,mass=fullfraction[j,c],common_target=fulltarget[c],overlap_mass=full_overlap))
    table('sample_summary.tsv',summaries);table('full_common_support.tsv',fullrows)
    groups=[]
    for scope,base in [('all_selected',np.ones(len(inverse),bool)),('primary',primary)]:
        for t in TUNES:
            tm=(d['tune']==t)&base
            groups.append((scope,t,'all',tm,d['weight']))
            for comp in ['pi','k','charm']:groups.append((scope,t,comp,tm&(d['component']==comp),d['weight']))
            for lo,hi in zip(EDGES[:-1],EDGES[1:]):
                groups.append((scope,t,f'E{lo:g}_{hi:g}',tm&(d['truth_E_GeV']>=lo)&(d['truth_E_GeV']<hi),d['weight']))
            for layer,m in [('lowpz',(d['reco_pz_GeV']<100)),('lowpz_highE',(d['reco_pz_GeV']<100)&(d['truth_E_GeV']>=200)),('high_y',d['y_lepton']>=.8),('unconfirmed',~d['confirmed']),('nu',d['incoming'][:,0]==14),('antinu',d['incoming'][:,0]==-14),('upstream',d['vertex_z_mm']<-2200),('downstream_box',(d['vertex_z_mm']>=-2200)&(d['vertex_z_mm']<-1950)),('lead_block',d['vertex_z_mm']>=-1950)]:
                groups.append((scope,t,layer,tm&m,d['weight']))
    for scope,weight_name in [('standardized','standard_weight'),('fully_standardized','matched_weight')]:
        for t in TUNES:
            for layer,m in [('all',np.ones(len(inverse),bool))]+[(f'E{lo:g}_{hi:g}',(d['truth_E_GeV']>=lo)&(d['truth_E_GeV']<hi)) for lo,hi in zip(EDGES[:-1],EDGES[1:])]:
                groups.append((scope,t,layer,(d['tune']==t)&primary&m,d[weight_name]))
    # Shared Poisson(1) incoming multipliers preserve cross-tune correlation.
    rng=np.random.default_rng(2026110625);B=500
    multiplier=rng.poisson(1,(B,len(keys))).astype('float32')
    bootstrap={};point={}
    for scope,t,layer,mask,weights in groups:
        mask=mask&(weights>0);use=np.flatnonzero(mask)
        if not len(use):continue
        w=weights[use];ids=inverse[use];unique,local=np.unique(ids,return_inverse=True)
        den=np.bincount(local,weights=w);bd=multiplier[:,unique]@den
        for model in ['direct','traditional']:
            e=d[model+'_logE'][use]-np.log(d['truth_E_GeV'][use]);out=metrics(e,w)
            row=dict(scope=scope,tune=t,stratum=layer,model=model,N=len(use),incoming=len(unique),weight_sum=float(w.sum()),ESS=float(w.sum()**2/np.dot(w,w)),**out)
            bs={}
            for name,value in [('log_RMSE',e*e),('tail50_pct',100*(abs(np.expm1(e))>.5)),('mean_log_bias',e)]:
                num=np.bincount(local,weights=w*value,minlength=len(unique));v=(multiplier[:,unique]@num)/np.where(bd>0,bd,np.nan)
                if name=='log_RMSE':v=np.sqrt(v)
                lo,hi=np.nanquantile(v,[.025,.975]);row[name+'_low95']=float(lo);row[name+'_high95']=float(hi);bs[name]=v
            allrows.append(row);bootstrap[scope,t,layer,model]=bs;point[scope,t,layer,model]=out
    table('metrics.tsv',allrows)
    contrast=[]
    for scope in ['primary','standardized','fully_standardized']:
        for t in TUNES:
            for layer in ['all']+[f'E{lo:g}_{hi:g}' for lo,hi in zip(EDGES[:-1],EDGES[1:])]:
                for model in ['direct','traditional']:
                    a=(scope,t,layer,model);b=(scope,'JEFF33',layer,model)
                    if a not in bootstrap or b not in bootstrap:continue
                    for name in ['log_RMSE','tail50_pct','mean_log_bias']:
                        v=bootstrap[a][name]/bootstrap[b][name] if name=='log_RMSE' else bootstrap[a][name]-bootstrap[b][name]
                        value=point[a][name]/point[b][name] if name=='log_RMSE' else point[a][name]-point[b][name]
                        lo,hi=np.nanquantile(v,[.025,.975]);contrast.append(dict(scope=scope,tune=t,reference='JEFF33',stratum=layer,model=model,quantity=name,estimate=value,low95=lo,high95=hi))
    table('tune_contrasts.tsv',contrast)
    model_comparison=[]
    for scope,t,layer,_mask,_weights in groups:
        a=(scope,t,layer,'direct');b=(scope,t,layer,'traditional')
        if a not in bootstrap or b not in bootstrap:continue
        for name in ['log_RMSE','tail50_pct']:
            v=bootstrap[a][name]/bootstrap[b][name] if name=='log_RMSE' else bootstrap[a][name]-bootstrap[b][name]
            value=point[a][name]/point[b][name] if name=='log_RMSE' else point[a][name]-point[b][name]
            lo,hi=np.nanquantile(v,[.025,.975])
            model_comparison.append(dict(scope=scope,tune=t,stratum=layer,quantity=name,estimate=value,low95=lo,high95=hi))
    table('direct_vs_traditional.tsv',model_comparison)
    # Same incoming and common-selected response comparisons, not efficiencies.
    paired=[]
    for t in TUNES:
        if t=='JEFF33':continue
        ia=np.flatnonzero((d['tune']==t)&primary);ib=np.flatnonzero((d['tune']=='JEFF33')&primary)
        shared=np.intersect1d(inverse[ia],inverse[ib]);setshared=set(shared.tolist())
        for model in ['direct','traditional']:
            views=[]
            for ix in [ia,ib]:
                ix=np.array([i for i in ix if inverse[i] in setshared],int);u,inv,cnt=np.unique(inverse[ix],return_inverse=True,return_counts=True)
                log=d[model+'_logE'][ix];mean=np.bincount(inv,weights=log)/cnt
                views.append((u,mean))
            np.testing.assert_array_equal(views[0][0],views[1][0]);delta=views[0][1]-views[1][1]
            paired.append(dict(tune=t,reference='JEFF33',model=model,common_selected_incoming=len(shared),
                               tune_selected_incoming=len(np.unique(inverse[ia])),reference_selected_incoming=len(np.unique(inverse[ib])),
                               median_log_response_shift=float(np.median(delta)) if len(delta) else np.nan,
                               R68_log_shift=float(np.diff(np.quantile(delta,[.16,.84]))[0]/2) if len(delta) else np.nan,
                               RMS_log_shift=float(np.sqrt(np.mean(delta**2))) if len(delta) else np.nan))
    table('paired_incoming.tsv',paired)
    quality=[]
    for scheme,edges in [('paper',PAPER),('fine',EDGES)]:
        for t in TUNES:
            use=primary&(d['tune']==t);w=d['weight'][use];truth=d['truth_E_GeV'][use]
            for model in ['direct','traditional']:
                counts=np.histogram2d(np.exp(d[model+'_logE'][use]),truth,bins=(edges,edges),weights=w)[0]
                cols=counts.sum(0);norm=np.divide(counts,cols[None,:],out=np.zeros_like(counts),where=cols[None,:]>0)
                assert np.allclose(norm[:,cols>0].sum(0),1)
                for y,x in np.ndindex(counts.shape):matrices.append(dict(scheme=scheme,tune=t,model=model,true_bin=x,reco_bin=y,weighted_count=counts[y,x],probability=norm[y,x],truth_weight=cols[x]))
                truebin=np.searchsorted(edges,truth,side='right')-1;recobin=np.searchsorted(edges,np.exp(d[model+'_logE'][use]),side='right')-1
                for b in range(len(edges)-1):
                    col=truebin==b;row=recobin==b
                    quality.append(dict(scheme=scheme,tune=t,model=model,bin=b,
                                        truth_selected_views=int(col.sum()),truth_incoming=len(np.unique(inverse[use][col])),
                                        truth_weight=float(w[col].sum()),reco_selected_views=int(row.sum()),
                                        stability_pct=100*norm[b,b] if cols[b]>0 else np.nan,
                                        purity_pct=100*counts[b,b]/counts[b].sum() if counts[b].sum()>0 else np.nan,
                                        all_bin_agreement_pct=100*np.dot(w,truebin==recobin)/w.sum()))
    table('matrices.tsv',matrices)
    table('migration_quality.tsv',quality)
    # Compact reusable prediction cache: no ROOT/xAOD, no duplicated feature X.
    np.savez_compressed(CACHE/'evaluation.npz',**{k:v for k,v in d.items() if k!='x'})
    np.savez_compressed(CACHE/'reference.npz',**reference_data)
    np.savez_compressed(CACHE/'selected_inputs.npz',**{k:v for k,v in d.items() if k in ['x','incoming','truth_E_GeV','reco_pz_GeV','run','eventID','input_entry','y_lepton','primary_valid','confirmed','vertex_z_mm','source','tune','component','probability']})
    validation=dict(stage87_reference_exact=True,stage87_test=reference,new_model_fits=0,new_calibration_fits=0,
                    complete_source_inventory=len(support)==len(plan['sources']),
                    model_seeds=plan['seeds'],offset_log=plan['offset_log'],sources=len(support),
                    selected_N=len(inverse),primary_N=int(primary.sum()),fit_overlap_N=int(d['fit_overlap'].sum()),
                    common_component_energy_overlap_mass=overlap,bootstrap_replicates=B,
                    common_component_energy_y_depth_overlap_mass=full_overlap,
                    source_dependence=graph,
                    reference_inference_wall_s=reference_inference_wall_s,
                    new_inference_wall_s=new_inference_wall_s,
                    new_inference_events_per_s=len(inverse)/new_inference_wall_s,
                    bootstrap_scope=plan['uncertainty'],wall_s=time.perf_counter()-start,CPU_s=time.process_time()-cpu,
                    RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (OUT/'validation.json').write_text(json.dumps(validation,indent=2)+'\n');print(json.dumps(validation),flush=True)


if __name__=='__main__':main()
