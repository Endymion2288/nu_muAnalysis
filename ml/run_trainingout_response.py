#!/usr/bin/env python3
"""One stage66 Condor job, cal-template only and 500 paired source draws."""
import json
import traceback
import numpy as np
from trainingout_response import (OUT,REPO,REPRESENTATIONS,TERMS,COMPONENTS,
    FISHER_FIELDS,PROJECTION_FIELDS,grouped_moments,source_draws,source_ess,decompose,
    local_information,response_vectors,project_response,table,numeric,uncertainty,
    begin,resources,save)


def main():
    start=begin();assert not (OUT/'summary.json').exists(),'No repeat formal stage66'
    p=json.loads((OUT/'protocol.json').read_text());B=p['bootstrap_replicates'];f=p['f_eval']
    with np.load(REPO/p['input_cache']) as z:d={k:z[k] for k in z.files}
    previous=json.loads((REPO/'workbook/stage65_energy_ml/summary.json').read_text())
    protected=[]
    for role in ['train','cal','eval']:
        take=d['role']==role
        row=dict(role=role,N=int(take.sum()),sources=len(np.unique(d['group'][take])),
            low_N=int(d['low'][take].sum()),missing_inputs_N=int(d['missing'][take].sum()),
            unconfirmed_N=int((~d['confirmed'][take]).sum()),negative_correction_N=int((d['S'][take]<d['M'][take]).sum()))
        assert row==next(r for r in previous['protected_counts'] if r['role']==role)
        protected.append(row)
    assert f==float(d['low'][d['role']=='eval'].mean())
    central={};bootstrap={};groups_by_role={};arrays={};ess_rows=[];source_counts={}
    for role in ['cal','eval']:
        groups,counts,logs=grouped_moments(d,p,role);groups_by_role[role]=groups.tolist()
        draws=source_draws(groups,p['bootstrap_seeds'][role],B);central[role]={};bootstrap[role]={}
        arrays[role+'_ESS']=source_ess(draws,counts['M_mu'])
        for j,component in enumerate(['all','low','high']):
            nominal=counts['M_mu'].sum() if j==0 else counts['M_mu'][:,j-1].sum()
            ess_rows.append(dict(role=role,component=component,nominal_N=int(nominal),**uncertainty(arrays[role+'_ESS'][:,j])))
        source_counts[role]=(counts['M_mu'].sum(axis=3)>0).sum(axis=0)
        for name in REPRESENTATIONS:
            central[role][name]=(counts[name].sum(axis=0),logs[name].sum(axis=0))
            bootstrap[role][name]=(np.einsum('bg,gckz->bckz',draws,counts[name]),np.einsum('bg,gkz->bkz',draws,logs[name]))
        arrays[role+'_stratum_counts']=bootstrap[role]['M_mu'][0].sum(axis=3)
    np.testing.assert_array_equal(central['cal']['M_mu'][0].sum(axis=(1,2)),p['expected_template_low_high'])
    np.testing.assert_array_equal(central['eval']['M_mu'][0].sum(axis=(1,2)),p['expected_target_low_high'])
    support=[];nt=central['cal']['M_mu'][0].sum(axis=2);nr=central['eval']['M_mu'][0].sum(axis=2)
    bt=arrays['cal_stratum_counts'];br=arrays['eval_stratum_counts']
    for c,component in enumerate(['low','high']):
        for k in range(nt.shape[1]):
            support.append(dict(component=component,stratum=k,energy_bin=k//3,production=p['production_components'][k%3],
                cal_N=int(nt[c,k]),cal_sources=int(source_counts['cal'][c,k]),eval_N=int(nr[c,k]),eval_sources=int(source_counts['eval'][c,k]),
                shared=bool(nt[c,k]>0 and nr[c,k]>0),bootstrap_cal_zero_N=int((bt[:,c,k]==0).sum()),
                bootstrap_eval_zero_N=int((br[:,c,k]==0).sum()),bootstrap_shared_N=int(((bt[:,c,k]>0)&(br[:,c,k]>0)).sum())))
    table(OUT/'support.csv',support);table(OUT/'source_ESS.csv',ess_rows)
    fishers=[];intervals=[];shifts=[];residuals=[];vectors=[];models=[];strata=[];unmatched=[]
    worst_C=0.;worst_operator=0.;worst_conservation=0.
    for name in REPRESENTATIONS:
        t,h=central['cal'][name];r=central['eval'][name][0];dec=decompose(t,r)
        arrays[name+'_unmatched_mass']=np.stack([decompose(bootstrap['cal'][name][0][b],bootstrap['eval'][name][0][b])['unmatched_mass'] for b in range(B)])
        for c,component in enumerate(['low','high']):
            for j,role in enumerate(['cal','eval']):
                unmatched.append(dict(representation=name,component=component,role=role,central=float(dec['unmatched_mass'][c,j]),**uncertainty(arrays[name+'_unmatched_mass'][:,c,j])))
        for c,component in enumerate(['low','high']):
            for j,term in enumerate(TERMS):
                for z,value in enumerate(dec['vectors'][c,j]):vectors.append(dict(representation=name,component=component,term=term,bin=z,delta_probability=float(value)))
        for finite in [False,True]:
            key=f'{name}_{"finite" if finite else "known"}'
            info,D,W,op1,op2=local_information(t.sum(axis=1),h.sum(axis=0),f,p,finite)
            v=response_vectors(dec,f);projection=project_response(v,D,W,op1,op2)
            binfo=np.full((B,len(FISHER_FIELDS)),np.nan);bp=np.full((B,3,4,len(PROJECTION_FIELDS)),np.nan)
            for b in range(B):
                tc,th=bootstrap['cal'][name][0][b],bootstrap['cal'][name][1][b]
                bi,bD,bW,bo1,bo2=local_information(tc.sum(axis=1),th.sum(axis=0),f,p,finite)
                binfo[b]=[numeric(bi[field]) for field in FISHER_FIELDS]
                bd=decompose(tc,bootstrap['eval'][name][0][b]);bv=response_vectors(bd,f)
                result=project_response(bv,bD,bW,bo1,bo2)
                for j,field in enumerate(PROJECTION_FIELDS):bp[b,:,:,j]=result[field]
                worst_C=max(worst_C,abs(bi['C_sum']));worst_conservation=max(worst_conservation,bd['conservation_error'])
                if bi['unit_operator_error'] is not None:worst_operator=max(worst_operator,bi['unit_operator_error'])
            row=dict(template_role='cal',point='eval',representation=name,**info)
            for mode in ['fixed','free']:
                shift=projection[mode+'_delta_f'][2,3];samples=f+bp[:,2,3,PROJECTION_FIELDS.index(mode+'_delta_f')]
                row[mode+'_linear_f_outside_range']=bool(np.isfinite(shift) and not 0<=f+shift<=1)
                row[mode+'_bootstrap_f_outside_range_N']=int(((samples<0)|(samples>1)).sum())
                row[mode+'_bootstrap_invalid_N']=int((~np.isfinite(samples)).sum())
            fishers.append(row)
            models.append(dict(representation=name,finite_MC=finite,D=D.tolist(),inverse_covariance=W.tolist(),
                fixed_operator=op1.tolist() if op1 is not None else None,free_operator=op2.tolist() if op2 is not None else None))
            for j,field in enumerate(FISHER_FIELDS):intervals.append(dict(representation=name,finite_MC=finite,quantity=field,central=info[field],**uncertainty(binfo[:,j])))
            arrays[key+'_Fisher']=binfo;arrays[key+'_projection']=bp
            for c,component in enumerate(COMPONENTS):
                for j,term in enumerate(TERMS):
                    for k,field in enumerate(PROJECTION_FIELDS):
                        value=projection[field][c,j]
                        shifts.append(dict(representation=name,finite_MC=finite,component=component,term=term,quantity=field,central=float(value) if np.isfinite(value) else None,**uncertainty(bp[:,c,j,k])))
                    for mode in ['fixed','free']:
                        for z,value in enumerate(projection[mode+'_residual'][c,j]):
                            residuals.append(dict(representation=name,finite_MC=finite,component=component,term=term,mode=mode,bin=z,delta_probability=float(value) if np.isfinite(value) else None))
            # Central signed conditional contributions identify support needs, not cuts.
            for c,component in enumerate(['low','high']):
                for k in range(t.shape[1]):
                    raw=dec['by_k'][c,1,k]*[f,1-f][c]
                    projected=project_response(raw,D,W,op1,op2)
                    strata.append(dict(representation=name,finite_MC=finite,component=component,stratum=k,
                        **{field:float(projected[field]) if np.isfinite(projected[field]) else None for field in ['fixed_delta_f','free_delta_f','free_delta_alpha']}))
            print(key,'rank',info['normalized_rank'],'free_invalid',row['free_bootstrap_invalid_N'],flush=True)
    assert max(worst_C,worst_operator,worst_conservation)<p['numerical_tolerance']
    save(OUT/'summary.json',dict(Fisher=fishers,protected_counts=protected,source_groups=groups_by_role,
        max_C_normalization_error=worst_C,max_operator_identity_error=worst_operator,max_decomposition_conservation_error=worst_conservation,
        bootstrap_replicates=B,Fisher_bootstrap_fields=FISHER_FIELDS,projection_bootstrap_fields=PROJECTION_FIELDS,
        new_train_draws=0,energy_fits=0,F7_inferences=0,nonlinear_profiles=0))
    save(OUT/'models.json',models)
    scalar=['representation','finite_MC','f','regular','normalized_rank','normalized_condition','parameter_correlation',
        'sigma_f_fixed','sigma_f_free','sigma_alpha','sigma_r_over_r_fixed','sigma_r_over_r_free','sigma_f_cost_ratio']
    table(OUT/'Fisher.csv',[{key:row[key] for key in scalar} for row in fishers])
    for filename,rows in [('Fisher_intervals.csv',intervals),('projections.csv',shifts),('residuals.csv',residuals),('vectors.csv',vectors),('conditional_strata.csv',strata),('unmatched_support.csv',unmatched)]:table(OUT/filename,rows)
    np.savez_compressed(OUT/'bootstrap.npz',**arrays)
    save(OUT/'batch_resources.json',resources(start))


if __name__=='__main__':
    try:main()
    except Exception:
        (OUT/'failure.txt').write_text(traceback.format_exc());raise
