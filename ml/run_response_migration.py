#!/usr/bin/env python3
"""One bounded source-bootstrap job, fixed M/S; no new fits or inference."""
import csv
import json
import traceback
import numpy as np

from response_migration import (OUT,REPO,REPRESENTATIONS,TERMS,COMPONENTS,decompose,
    linear_operator,project,group_counts,source_draws,source_ess,begin,resources,save)


def table(path,rows):
    with path.open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def interval(values):
    return dict(low95=float(np.quantile(values,.025)),high95=float(np.quantile(values,.975)))


def main():
    start=begin();assert not (OUT/'summary.json').exists(),'Immutable formal stage64 result'
    p=json.loads((OUT/'protocol.json').read_text());prior=REPO/'workbook/stage63_energy_ml'
    with np.load(REPO/p['input_cache']) as z:d={k:z[k] for k in z.files}
    fits=json.loads((prior/'fits.json').read_text());old_templates=json.loads((prior/'templates.json').read_text())
    grouped={};draws={};central={};boot={};ess={};support=[];protected=[]
    K=(len(p['truth_E_edges_GeV'])+1)*3
    for role,N,G in [('train',41447,91),('cal',8440,16),('eval',14057,22)]:
        take=d['role']==role;groups,gid,layer,counts=group_counts(d,p,role)
        assert take.sum()==N and len(groups)==G
        grouped[role]=groups;draws[role]=source_draws(groups,p['bootstrap_seeds'][role],p['bootstrap_replicates'])
        central[role]={name:value.sum(axis=0) for name,value in counts.items()}
        boot[role]={name:np.einsum('bg,gckz->bckz',draws[role],value) for name,value in counts.items()}
        ess[role]=source_ess(draws[role],counts['M_mu'])
        protected.append(dict(role=role,N=N,sources=G,low_N=int(d['low'][take].sum()),
            missing_inputs_N=int(d['missing'][take].sum()),unconfirmed_N=int((~d['confirmed'][take]).sum()),
            negative_correction_N=int((d['S'][take]<d['M'][take]).sum())))
        lo=d['low'][take];same_p=(d['pz'][take]>=50)&(d['pz'][take]<100)
        for c,low in enumerate([True,False]):
            for k in range(K):
                use=(lo==low)&(layer==k);number=int(use.sum());source_N=len(np.unique(gid[use]))
                row=dict(role=role,truth_component=COMPONENTS[c],stratum=k,energy_bin=k//3,
                    production=p['production_components'][k%3],N=number,sources=source_N,unit_ESS=number,
                    thin_support=bool(number<20 or source_N<3),
                    reco_pz50_100_N=int((use&same_p).sum()),high_y_N=int((use&(d['y_lepton'][take]>=.8)).sum()),
                    same_p_high_y_N=int((use&same_p&(d['y_lepton'][take]>=.8)).sum()),
                    unconfirmed_N=int((use&~d['confirmed'][take]).sum()),missing_N=int((use&d['missing'][take]).sum()),
                    negative_correction_N=int((use&(d['S'][take]<d['M'][take])).sum()))
                for name in REPRESENTATIONS:
                    h=central[role][name][c,k];row['zero_cells_'+name]=int((h==0).sum())
                support.append(row)
    operators={};projections=[];norms=[];vectors=[];strata_rows=[];linear_checks=[];unmatched_rows=[];arrays={}
    worst=0.;worst_projection=0.
    for role in ['cal','eval']:
        take=d['role']==role;f=float(d['low'][take].mean())
        for name in REPRESENTATIONS:
            t=central['train'][name];r=central[role][name];mc=t.sum(axis=1)
            for c,key in [(0,'low_MC_N'),(1,'high_MC_N')]:
                old=[x[key] for x in old_templates if x['representation']==name]
                np.testing.assert_array_equal(mc[c],old)
            op,diag=linear_operator(mc,f,p['fixed_N_selected']);operators[role+'_'+name]=dict(f_true=f,weights=op.tolist(),**diag)
            dec=decompose(t,r);pr=project(dec['vectors'],op,f);worst=max(worst,dec['conservation_error'])
            by_k=np.einsum('ctkz,z->ctk',dec['by_k'],op)*np.array([f,1-f])[:,None,None]
            B=p['bootstrap_replicates'];bp=np.empty((B,3,4));bn=np.empty((B,2,4));bu=np.empty((B,2,2));bk=np.empty((B,2,3,K))
            for b in range(B):
                boot_dec=decompose(boot['train'][name][b],boot[role][name][b])
                bp[b]=project(boot_dec['vectors'],op,f);bn[b]=boot_dec['half_L1'];bu[b]=boot_dec['unmatched_mass']
                bk[b]=np.einsum('ctkz,z->ctk',boot_dec['by_k'],op)*np.array([f,1-f])[:,None,None]
                worst=max(worst,boot_dec['conservation_error'])
                worst_projection=max(worst_projection,float(np.max(abs(bp[b,:,:3].sum(axis=1)-bp[b,:,3]))))
            original=next(x for x in fits if x['role']==role and x['source']=='pooled' and x['variant']=='nominal' and x['representation']==name and x['finite_MC'])
            existing_delta=original['f_hat']-f
            linear_checks.append(dict(role=role,representation=name,f_true=f,existing_profile_delta_f=existing_delta,
                linear_total_delta_f=float(pr[2,3]),profile_minus_linear_delta_f=float(existing_delta-pr[2,3]),**interval(bp[:,2,3])))
            for c,component in enumerate(COMPONENTS):
                for j,term in enumerate(TERMS):
                    projections.append(dict(role=role,representation=name,truth_component=component,term=term,
                        delta_f=float(pr[c,j]),**interval(bp[:,c,j])))
                    if c==2:continue
                    norms.append(dict(role=role,representation=name,truth_component=component,term=term,
                        half_L1=float(dec['half_L1'][c,j]),**interval(bn[:,c,j])))
                    for z,value in enumerate(dec['vectors'][c,j]):
                        vectors.append(dict(role=role,representation=name,truth_component=component,term=term,bin=z,delta_probability=float(value)))
                    if j==3:continue
                    for k in range(K):
                        strata_rows.append(dict(role=role,representation=name,truth_component=component,term=term,stratum=k,
                            energy_bin=k//3,production=p['production_components'][k%3],shared=bool(dec['shared'][c,k]),
                            delta_f=float(by_k[c,j,k]),**interval(bk[:,c,j,k])))
            for c in range(2):
                for side,sample in enumerate(['train',role]):
                    unmatched_rows.append(dict(role=role,representation=name,truth_component=COMPONENTS[c],sample=sample,
                        unmatched_mass=float(dec['unmatched_mass'][c,side]),**interval(bu[:,c,side])))
            arrays[role+'_'+name+'_projection']=bp;arrays[role+'_'+name+'_half_L1']=bn
            arrays[role+'_'+name+'_unmatched_mass']=bu
            print(role,name,'conservation',dec['conservation_error'],'bootstrap',B,flush=True)
    assert worst<p['conservation_tolerance'] and worst_projection<p['conservation_tolerance']
    for role,value in ess.items():arrays[role+'_source_ESS']=value
    save(OUT/'operators.json',operators)
    save(OUT/'summary.json',dict(projections=projections,linear_checks=linear_checks,unmatched=unmatched_rows,
        maximum_probability_conservation_error=worst,maximum_projection_conservation_error=worst_projection,
        protected_counts=protected,bootstrap_replicates=p['bootstrap_replicates'],
        source_groups={role:g.tolist() for role,g in grouped.items()},
        bootstrap_ESS={role:[dict(scope=label,**interval(value[:,j]),minimum=float(value[:,j].min()),maximum=float(value[:,j].max())) for j,label in enumerate(['all','low','high'])] for role,value in ess.items()},
        new_profiles=0,energy_fits=0,F7_inferences=0))
    for filename,rows in [('projection.csv',projections),('component_norms.csv',norms),('vectors.csv',vectors),
                          ('stratum_projection.csv',strata_rows),('support.csv',support),('linear_checks.csv',linear_checks),('unmatched_support.csv',unmatched_rows)]:table(OUT/filename,rows)
    np.savez_compressed(OUT/'bootstrap.npz',**arrays)
    save(OUT/'batch_resources.json',resources(start))


if __name__=='__main__':
    try:main()
    except Exception:
        (OUT/'failure.txt').write_text(traceback.format_exc());raise
