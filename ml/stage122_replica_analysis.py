"""Batch-only native round-trip and fixed-model same-HITS response diagnostics."""
import argparse
import gzip
import json
import zlib
from pathlib import Path

import numpy as np

from audited_features import configuration,WAVE_INVALID
from stage122_compare import table,load,OUT,CACHE,ROOT


def read(name):
    with gzip.open(CACHE/name,'rt') as f:return json.load(f)


def primary(rows):
    # Ntuple branch buffers are zero-initialized, even for an absent container.
    result={}
    for h in rows:
        if not int(h[2])&2:result[int(h[1])]=h
    return result


def reference_channels(index):
    r=read(f'referencemap_{index}.json.gz')
    assert r['configuration']['database_instance']=='OFLP200'
    assert r['configuration']['global_tag']=='OFLCOND-FASER-06'
    rows=r['events'][0]['veto_cable_map']
    channels=[v[0] for v in rows if v[2]==1]
    assert channels
    return channels,rows


def summaries(reconstructed,veto_channels):
    p={k:primary(v) for k,v in reconstructed.items()};out={};secondary=max(0,len(reconstructed['VetoNu'])-2)
    for detector,channels in [('VetoNu',[4,5]),('Preshower',[12,13])]:
        for j,ch in enumerate(channels):
            h=p[detector].get(ch);raw=h[3] if h else 0.;status=int(h[2]) if h else 0
            out[f'{detector}{j}_raw_charge']=np.float32(np.nan if status&WAVE_INVALID else raw)
            out[f'{detector}{j}_charge']=np.float32(h[4] if h else 0.)
            out[f'{detector}{j}_status']=status
    def mean_time(detector,channels):
        good=[h[5] for h in reconstructed[detector] if int(h[2])==0 and int(h[1]) in channels]
        t=np.float32(0)
        for v in good:t=np.float32(t+np.float32(v))
        return np.float32(t/len(good)) if good else np.nan
    vt=mean_time('Veto',veto_channels);pt=mean_time('Preshower',list(p['Preshower']))
    # faser_ntuple_maker.py at the frozen d32b0ff3 revision overrides the
    # class defaults for MC. These are producer constants, not QA fit values.
    # The expected time is float, but adding the Gaudi DoubleProperty window
    # promotes it to double. Avoid NumPy scalar promotion rounding a boundary.
    limit=float(np.float32(float(vt)-27.21 if np.isfinite(vt) else float(pt)-51.41))+35.
    reduced=[np.float32(0),np.float32(0)]
    if not np.isfinite(vt) and not np.isfinite(pt):
        reduced=[np.float32(p['VetoNu'].get(ch,[0,0,0,0])[3]) for ch in [4,5]]
    else:
        # Native producer indexes by container ordinal, not channel. Retain first
        # two slots; explicitly count extra hits because its fixed array is size2.
        for j,h in enumerate(reconstructed['VetoNu']):
            if j>=2:continue
            n=int(h[6]);times=h[7:7+n];values=h[7+n:];assert len(values)==n
            total=np.float32(0)
            for t,v in zip(times,values):
                if t>=limit:break
                total=np.float32(total+np.float32(v))
            reduced[j]=np.float32(total*np.float32(2/50))
    for j in [0,1]:out[f'VetoNu{j}_reduced_charge']=np.float32(np.nan if out[f'VetoNu{j}_status']&WAVE_INVALID else reduced[j])
    selected=all(out[f'Preshower{j}_charge']>2.5 and reduced[j]<30 for j in [0,1])
    return out,selected,secondary


def compare_scalar(values,reference,names,rows):
    max_abs=0.;count=0
    for name,v in values.items():
        if name not in names:continue
        want=reference[names.index(name)];a,b=float(v),float(want)
        assert np.isnan(a)==np.isnan(b),(rows,name,a,b)
        if np.isfinite(a):
            delta=abs(a-b);max_abs=max(delta,max_abs)
            assert np.isclose(a,b,rtol=2e-5,atol=2e-5),(rows,name,a,b,delta)
        count+=1
    return max_abs,count


def qa():
    a,b=read('recoqa10_0.json.gz'),read('replaymc3_0.json.gz')
    assert a['events'][:len(b['events'])]==b['events'],'Cross-process MC replay differs'
    names=configuration()['features'];d=load(CACHE/'cohort_input.npz');r=read('recoqa10_0.json.gz');checks=[]
    veto_channels,_=reference_channels(0)
    for row in r['events']:
        pos=np.flatnonzero((d['source_index']==36)&(d['input_entry']==row['entry']));assert len(pos)==1
        values,selected,extra=summaries(row['original_reconstructed'],veto_channels)
        delta,n=compare_scalar(values,d['x'][pos[0]],names,row['entry'])
        assert selected,(row['entry'],'Original selection mismatch')
        checks.append(dict(entry=row['entry'],checked_features=n,max_abs_pC=delta,extra_VetoNu_hits=extra,selection_equal=True))
    table('reconstruction_qa.tsv',checks)
    report=dict(cross_process_replay_parents=len(b['events']),cross_process_full_ADC_and_state_equal=True,
                native_roundtrip_parents=len(checks),max_abs_pC=max(v['max_abs_pC'] for v in checks),extra_VetoNu_hits=sum(v['extra_VetoNu_hits'] for v in checks),
                tolerance='rtol2e-5 atol2e-5pC; original typed float32 features, signed retained')
    (OUT/'reconstruction_qa.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)


def diagnose():
    names=configuration()['features'];p=json.loads((OUT/'replica_contract.json').read_text());rows=[]
    for si,source in enumerate(p['sources']):
        r=read(f'replicas_{si}.json.gz');paths=load(CACHE/f'candidates_{si}/paths.npz');c=load(CACHE/f'candidates_{si}/candidates.npz')
        veto_channels,_=reference_channels(si)
        for j,row in enumerate(r['events']):
            if not paths['other'][j]:continue
            ci=np.flatnonzero(c['input_entry']==j);assert len(ci)==1
            values,passed,extra=summaries(row['original_reconstructed'],veto_channels);reference=c['x'][ci[0]]
            for name,value in values.items():
                if name not in names:continue
                want=reference[names.index(name)]
                if np.isclose(value,want,rtol=2e-5,atol=2e-5,equal_nan=True):continue
                rows.append(dict(index=si,case=j,entry=row['entry'],feature=name,computed=float(value),reference=float(want),extra_VetoNu_hits=extra,
                    reconstructed={det:[h[:7] for h in hh] for det,hh in row['original_reconstructed'].items()},
                    VetoNu_vectors=[dict(times=h[7:7+int(h[6])],wave=h[7+int(h[6]):]) for h in row['original_reconstructed']['VetoNu']]))
    (OUT/'roundtrip_diagnostic.json').write_text(json.dumps(rows,indent=2)+'\n');print('scalar mismatches',len(rows),flush=True)


def full():
    import xgboost as xgb
    from stage119_curve_common import weights,masks
    names=configuration()['features'];p=json.loads((OUT/'replica_contract.json').read_text())
    old=load(ROOT/'ntuples/energy_ml_stage119/old_input.npz');roles={};isolated=set()
    for inc,role,run,event in zip(old['incoming'],old['role'],old['run'],old['eventID']):
        if role:roles[tuple(inc)]=max(roles.get(tuple(inc),0),int(role))
        else:isolated.add((int(run),int(event)))
    models=[];protocol=json.loads((ROOT/'workbook/stage87_energy_ml/protocol.json').read_text())
    for seed in protocol['baseline']['seeds']:
        m=xgb.Booster(params={'nthread':1});m.load_model(ROOT/f'ml/artifacts/stage87/direct_{seed}.ubj');assert m.feature_names==names;models.append(m)
    offset_data=load(ROOT/'ml/artifacts/stage87/predictions.npz');offset=float((offset_data['direct_cal']-offset_data['direct_raw'])[0])
    cohort=load(CACHE/'cohort_input.npz');parents=[];xs=[];slots=[];validations=[];native_cost=[];reference_maps=[]
    for si,source in enumerate(p['sources']):
        r=read(f'replicas_{si}.json.gz');paths=load(CACHE/f'candidates_{si}/paths.npz');c=load(CACHE/f'candidates_{si}/candidates.npz')
        veto_channels,mapping=reference_channels(si)
        reference_maps.extend(dict(index=si,channel=v[0],current_id32=v[1],station=v[2],plate=v[3],used_for_Veto2_time=v[0] in veto_channels) for v in mapping)
        assert [v['entry'] for v in r['events']]==paths['entry'].tolist()
        assert len(r['events'])==len(source['cases'])
        native_cost.append(dict(index=si,N=len(r['events']),CPU_s=r['CPU_s'],wall_s=r['wall_s'],RSS_KiB=r['RSS_KiB'],read_bytes=r['read_bytes']))
        candidate_index={int(j):k for k,j in enumerate(c['input_entry'])}
        for j,(case,row) in enumerate(zip(source['cases'],r['events'])):
            np.testing.assert_array_equal(np.asarray(row['incoming'],dtype='float32'),paths['incoming'][j].astype('float32'))
            key=tuple(paths['incoming'][j]);role=0 if (source['run'],row['event']) in isolated else roles.get(key,1+int(zlib.crc32(np.asarray(key,dtype='<f8').tobytes()+b'stage122')%100>=70)+int(zlib.crc32(np.asarray(key,dtype='<f8').tobytes()+b'stage122')%100>=85))
            other=bool(paths['other'][j]);nominal=bool(paths['nominal'][j]);values,spass,extra=summaries(row['original_reconstructed'],veto_channels)
            assert (other and spass)==nominal,(si,j,'native selection roundtrip')
            checked=0;delta=0.
            if other:
                assert j in candidate_index
                x=c['x'][candidate_index[j]].copy();delta,checked=compare_scalar(values,x,names,(si,j))
                original_pos=np.flatnonzero((cohort['source_index']==source['source_index'])&(cohort['input_entry']==case['entry']))
                if len(original_pos):
                    np.testing.assert_allclose(x,cohort['x'][original_pos[0]],rtol=2e-5,atol=2e-5,equal_nan=True)
                    # Freeze the exact already-used non-varied detector values.
                    x=cohort['x'][original_pos[0]].copy()
            validations.append(dict(index=si,entry=case['entry'],other_cuts=other,nominal=nominal,checked_features=checked,max_abs_pC=delta,original_extra_VetoNu_hits=extra))
            parent=dict(index=si,source_index=source['source_index'],entry=case['entry'],run=source['run'],event=row['event'],environment=source['environment'],component=source['component'],category=case['category'],pilot_selected=case['pilot_selected'],nominal=nominal,other_cuts=other,role=role,E_GeV=float(paths['E'][j]),y=float(paths['y'][j]),pz=float(paths['pz'][j]),weight=1/(source['file_probability']*case['inclusion_probability']),incoming=key,selected=[],extra_VetoNu_hits=0,Z=[np.nan]*16)
            parent.update(confirmed=bool(c['confirmed'][candidate_index[j]]) if other else None,primary_valid=bool(c['primary_valid'][candidate_index[j]]) if other else None,vertex_z_mm=float(row.get('vertex_mm',[np.nan]*3)[2]),input_missing=bool(np.isnan(x).any()) if other else None)
            pi=len(parents)
            if other and role:
                xs.append(x.copy());slots.append((pi,-1))
            for rep in range(16):
                rec={'Veto':row['original_reconstructed']['Veto']}
                for det in ['VetoNu','Preshower']:
                    reps=row['detectors'][det]['replicas'];assert reps[0]==reps[1]
                    rr=[v for v in reps if v['replica']==rep][0];rec[det]=rr['reconstructed']
                vv,passed,extra=summaries(rec,veto_channels);parent['selected'].append(bool(other and passed));parent['extra_VetoNu_hits']+=extra
                if other and role:
                    xx=x.copy()
                    for name,value in vv.items():
                        if name in names:xx[names.index(name)]=value
                    xs.append(xx);slots.append((pi,rep))
            parents.append(parent)
    if xs:
        dm=xgb.DMatrix(np.asarray(xs),feature_names=names);pred=np.mean([m.predict(dm).astype(float) for m in models],axis=0)+offset
        for (pi,rep),z in zip(slots,pred):
            if rep==-1:parents[pi]['original_Z']=float(z)
            else:parents[pi]['Z'][rep]=float(z)
    # Parent output mean is used only for variance decomposition, never deployed.
    parent_rows=[];identity_max=0.
    for v in parents:
        z=np.asarray(v['Z']);sel=np.asarray(v['selected']);finite=np.isfinite(z);base={k:vv for k,vv in v.items() if k not in ['Z','selected','incoming']}
        base.update(selected_N=int(sel.sum()),replicas=16,selection_probability=float(sel.mean()),migration=bool(np.any(sel!=v['nominal'])))
        if finite.any():
            assert finite.all();e=z-np.log(v['E_GeV']);var=float(np.var(z));bias=float(np.mean(e));mse=float(np.mean(e**2));identity_max=max(identity_max,abs(mse-var-bias**2));rel=np.expm1(e)
            base.update(output_log_variance=var,unbiased_log_variance=float(np.var(z,ddof=1)),mean_log_error=bias,mean_log_MSE=mse,mean_fractional_bias_pct=float(100*np.mean(rel)),tail50_pct=float(100*np.mean(abs(rel)>.5)),positive_tail50_pct=float(100*np.mean(rel>.5)),negative_tail50_pct=float(100*np.mean(rel<-.5)),stable_tail_all16=bool(np.all(abs(rel)>.5)))
            base.update(stable_positive_tail_all16=bool(np.all(rel>.5)),stable_negative_tail_all16=bool(np.all(rel<-.5)))
            base.update(original_log_error=float(v['original_Z']-np.log(v['E_GeV'])),repeat_mean_minus_original_log_prediction=float(np.mean(z)-v['original_Z']))
        parent_rows.append(base)
    assert identity_max<1e-12
    table('replica_parents.tsv',parent_rows);table('replica_validation.tsv',validations);table('replica_native_cost.tsv',native_cost);table('veto_reference_map.tsv',reference_maps)
    # Parent-cluster intervals; all16 streams remain correlated within a parent.
    points=[];migration=[];rng=np.random.default_rng(202611061224)
    for env in ['all','nominal','JEFF','ENDF']:
        for category in ['all','E50_100','E100_200','high_y_trueE200','transition200_400','natural_high_control','E200_inf','pz50_100','pz50_100_trueE200','high_y','unconfirmed','input_missing','upstream','highE']:
            def in_layer(v):
                if category=='all':return True
                if category=='E200_inf':return v['E_GeV']>=200
                if category=='pz50_100':return 50<=v['pz']<100
                if category=='pz50_100_trueE200':return 50<=v['pz']<100 and v['E_GeV']>=200
                if category=='high_y':return v['primary_valid'] and .8<=v['y']<1
                if category=='unconfirmed':return v['confirmed'] is False
                if category=='input_missing':return v['input_missing'] is True
                if category=='upstream':return v['vertex_z_mm']<-2200
                if category=='highE':return v['E_GeV']>=1000
                return v['category']==category
            ids=[j for j,v in enumerate(parents) if (env=='all' or v['environment']==env) and in_layer(v)]
            if not ids:continue
            pp=[parents[j] for j in ids];inc=np.asarray([v['incoming'] for v in pp]);w=np.asarray([v['weight'] for v in pp])*weights(inc)
            nominal=np.asarray([v['nominal'] for v in pp]);prob=np.asarray([np.mean(v['selected']) for v in pp]);other=np.asarray([v['other_cuts'] for v in pp])
            migration.append(dict(environment=env,stratum=category,parent_N=len(pp),other_cuts_N=int(other.sum()),nominal_pass_N=int(nominal.sum()),any_migration_N=int(np.sum([np.any(np.asarray(v['selected'])!=v['nominal']) for v in pp])),mean_selection_probability=float(np.average(prob,weights=w)),pass_to_fail_probability=float(np.average(nominal*(1-prob),weights=w)),fail_to_pass_probability=float(np.average((~nominal)*prob,weights=w))))
            for role in ['active',1,2,3]:
                ix=[j for j,v in enumerate(pp) if v['other_cuts'] and (v['role']>0 if role=='active' else v['role']==role)]
                if not ix:continue
                q=[pp[j] for j in ix];ww=w[ix];z=np.asarray([v['Z'] for v in q]);sel=np.asarray([v['selected'] for v in q]);e=z-np.log([v['E_GeV'] for v in q])[:,None];rel=np.expm1(e)
                _,first,gid=np.unique(np.asarray([v['incoming'] for v in q]),axis=0,return_index=True,return_inverse=True);nk=len(first);counts=np.zeros((500,nk),dtype=np.int16)
                components=np.asarray([v['component'] for v in q])[first]
                for component in sorted(set(components)):
                    use=np.flatnonzero(components==component);counts[:,use]=rng.multinomial(len(use),np.full(len(use),1/len(use)),size=500)
                draw=counts[:,gid]*ww
                for condition in ['all_valid_other_cuts','selected_realizations']:
                    mask=np.ones_like(sel) if condition=='all_valid_other_cuts' else sel;den=mask.mean(1);total=float(ww@den)
                    if total<=0:continue
                    fields=dict(log_MSE=(e**2*mask).mean(1),mean_log_error=(e*mask).mean(1),fractional_bias_pct=100*(rel*mask).mean(1),tail50_pct=100*((abs(rel)>.5)*mask).mean(1),positive_tail50_pct=100*((rel>.5)*mask).mean(1),negative_tail50_pct=100*((rel<-.5)*mask).mean(1))
                    row=dict(environment=env,stratum=category,role=role,condition=condition,parent_N=len(q),incoming=nk,replica_N=int(mask.sum()),ESS=float(total**2/np.sum((ww*den)**2)))
                    bden=draw@den;good=bden>0;row['valid_draws']=int(good.sum())
                    for name,value in fields.items():
                        point=float(ww@value/total);bt=(draw@value)[good]/bden[good]
                        if name=='log_MSE':name='log_RMSE';point=np.sqrt(point);bt=np.sqrt(bt)
                        row[name]=float(point)
                        if good.sum()>=475:row[name+'_low95'],row[name+'_high95']=map(float,np.quantile(bt,[.025,.975]))
                    if condition=='all_valid_other_cuts':
                        variance=np.var(z,axis=1);mse=(e**2).mean(1);row['mean_conditional_log_variance']=float(np.average(variance,weights=ww));row['variance_fraction_of_MSE']=float(ww@variance/(ww@mse));row['stable_tail_all16_N']=sum(bool(np.all(abs(a)>.5)) for a in rel)
                        row['stable_positive_tail_all16_N']=sum(bool(np.all(a>.5)) for a in rel)
                        row['stable_negative_tail_all16_N']=sum(bool(np.all(a<-.5)) for a in rel)
                        row['mean_parent_squared_log_bias']=float(np.average(e.mean(1)**2,weights=ww))
                        if good.sum()>=475:
                            row['mean_conditional_log_variance_low95'],row['mean_conditional_log_variance_high95']=map(float,np.quantile((draw@variance)[good]/bden[good],[.025,.975]))
                            row['variance_fraction_of_MSE_low95'],row['variance_fraction_of_MSE_high95']=map(float,np.quantile((draw@variance)[good]/(draw@mse)[good],[.025,.975]))
                    points.append(row)
    table('replica_risk.tsv',points);table('replica_migration.tsv',migration)
    make_plots(parent_rows)
    np.savez_compressed(CACHE/'replica_points.npz',Z=np.asarray([v['Z'] for v in parents]),selected=np.asarray([v['selected'] for v in parents]),incoming=np.asarray([v['incoming'] for v in parents]),role=np.asarray([v['role'] for v in parents]),E=np.asarray([v['E_GeV'] for v in parents]),weight=np.asarray([v['weight'] for v in parents]))
    report=dict(parent_N=len(parents),distinct_streams=16,forward_parent_N=sum(v['other_cuts'] and v['role']>0 for v in parents),forward_view_N=len(xs),original_control_forward_N=sum(rep==-1 for _,rep in slots),replica_forward_N=sum(rep>=0 for _,rep in slots),new_fits=0,expansion_reserved_predictions=0,quarantine_predictions=0,variance_identity_max_abs=identity_max,extra_VetoNu_hits=sum(v['extra_VetoNu_hits'] for v in parents),limitation='only VetoNu/Preshower digitization varies; tracker/calo/Veto/Timing fixed; finite16 conditional views not independent N, not Bayes error, no ensemble deployed')
    (OUT/'replica_summary.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)


def make_plots(parent_rows):
    import csv
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    metrics=list(csv.DictReader((OUT/'metrics.tsv').open(),delimiter='\t'))
    fig,axes=plt.subplots(1,2,figsize=(9,3.5))
    for ax,layer in zip(axes,['E50_100','E100_200']):
        rows=[next(r for r in metrics if r['role']=='3' and r['stratum']==layer and r['model']==m) for m in ['A','B','C','D','direct_cal','traditional']]
        y=np.array([float(r['log_RMSE']) for r in rows]);lo=np.array([float(r['RMSE_low95']) for r in rows]);hi=np.array([float(r['RMSE_high95']) for r in rows])
        ax.vlines(range(6),lo,hi);ax.plot(range(6),y,'o');ax.set_xticks(range(6),['A','B','C','D','f0','trad']);ax.set_title(layer+' GeV');ax.set_ylabel('log energy RMSE');ax.grid(alpha=.2)
    fig.suptitle('Developed response test cohort; conditional 95% intervals');fig.tight_layout();fig.savefig(OUT/'response_risk.svg');plt.close(fig)
    good=[r for r in parent_rows if 'mean_log_MSE' in r]
    fig,ax=plt.subplots(figsize=(6,4))
    for category in sorted(set(r['category'] for r in good)):
        q=[r for r in good if r['category']==category];ax.scatter([r['E_GeV'] for r in q],[r['output_log_variance']/r['mean_log_MSE'] if r['mean_log_MSE'] else 0 for r in q],s=20,label=category,alpha=.7)
    ax.set_xscale('log');ax.set_xlabel('True neutrino energy [GeV]');ax.set_ylabel('Conditional digitization variance / log MSE');ax.legend(fontsize=7);ax.grid(alpha=.2);fig.tight_layout();fig.savefig(OUT/'conditional_variance.svg');plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['qa','diagnose','full']);a=p.parse_args()
    {'qa':qa,'diagnose':diagnose,'full':full}[a.mode]()
