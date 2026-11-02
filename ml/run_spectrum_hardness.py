#!/usr/bin/env python3
"""One stage65 batch: local Fisher/projections and 500 paired source draws."""
import csv
import json
import traceback
import numpy as np

from spectrum_hardness import (OUT,REPO,REPRESENTATIONS,TERMS,COMPONENTS,
    grouped_moments,source_draws,decompose,local_information,response_vectors,
    project_response,begin,resources,save)

FISHER_FIELDS=['sigma_f_fixed','sigma_f_free','sigma_alpha','parameter_correlation',
              'sigma_f_cost_ratio','normalized_condition','normalized_rank','C_sum','unit_operator_error']
PROJECTION_FIELDS=['fixed_delta_f','free_delta_f','free_delta_alpha','fixed_half_L1',
                   'free_half_L1','fixed_weighted_norm','free_weighted_norm']


def table(path,rows):
    with path.open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def numeric(value):return np.nan if value is None else value


def uncertainty(values):
    use=np.isfinite(values);good=int(use.sum())
    return dict(low95=float(np.quantile(values[use],.025)) if good else None,
        high95=float(np.quantile(values[use],.975)) if good else None,
        valid_replicates=good,invalid_replicates=int((~use).sum()))


def main():
    start=begin();assert not (OUT/'summary.json').exists(),'No repeat formal stage65'
    p=json.loads((OUT/'protocol.json').read_text())
    with np.load(REPO/p['input_cache']) as z:d={k:z[k] for k in z.files}
    previous=json.loads((REPO/'workbook/stage64_energy_ml/summary.json').read_text())
    prior_ops=json.loads((REPO/'workbook/stage64_energy_ml/operators.json').read_text())
    stage63=json.loads((REPO/'workbook/stage63_energy_ml/protocol_v2.json').read_text());f0=stage63['f0']
    central={};bootstrap={};groups_by_role={};protected=[];B=p['bootstrap_replicates']
    for role in ['train','cal','eval']:
        groups,counts,logs=grouped_moments(d,p,role);groups_by_role[role]=groups.tolist()
        draws=source_draws(groups,p['bootstrap_seeds'][role],B)
        central[role]={};bootstrap[role]={}
        for name in REPRESENTATIONS:
            central[role][name]=(counts[name].sum(axis=0),logs[name].sum(axis=0))
            bootstrap[role][name]=(np.einsum('bg,gckz->bckz',draws,counts[name]),np.einsum('bg,gkz->bkz',draws,logs[name]))
        take=d['role']==role
        row=dict(role=role,N=int(take.sum()),sources=len(groups),low_N=int(d['low'][take].sum()),
            missing_inputs_N=int(d['missing'][take].sum()),unconfirmed_N=int((~d['confirmed'][take]).sum()),
            negative_correction_N=int((d['S'][take]<d['M'][take]).sum()))
        assert row==next(r for r in previous['protected_counts'] if r['role']==role)
        protected.append(row)
    fishers=[];intervals=[];shifts=[];residuals=[];models=[];arrays={};worst_C=0.;worst_operator=0.;worst_conservation=0.
    for point in ['reference','cal','eval']:
        f=f0 if point=='reference' else float(d['low'][d['role']==point].mean())
        for name in REPRESENTATIONS:
            t,tu=central['train'][name];mc=t.sum(axis=1);moment=tu.sum(axis=0)
            for finite in [False,True]:
                key=f'{point}_{name}_{"finite" if finite else "known"}'
                info,D,W,op1,op2=local_information(mc,moment,f,p,finite)
                binfo=np.full((B,len(FISHER_FIELDS)),np.nan)
                if point!='reference':
                    role_counts=central[point][name][0];dec=decompose(t,role_counts);v=response_vectors(dec,f)
                    projection=project_response(v,D,W,op1,op2)
                    bprojection=np.full((B,3,4,len(PROJECTION_FIELDS)),np.nan)
                    if finite:
                        old=next(r for r in previous['linear_checks'] if r['role']==point and r['representation']==name)
                        np.testing.assert_allclose(projection['fixed_delta_f'][2,3],old['linear_total_delta_f'],atol=1e-12,rtol=0)
                        np.testing.assert_allclose(op1,prior_ops[point+'_'+name]['weights'],atol=1e-10,rtol=0)
                for b in range(B):
                    bt=bootstrap['train'][name][0][b];blog=bootstrap['train'][name][1][b]
                    bi,bD,bW,bo1,bo2=local_information(bt.sum(axis=1),blog.sum(axis=0),f,p,finite)
                    binfo[b]=[numeric(bi[field]) for field in FISHER_FIELDS]
                    worst_C=max(worst_C,abs(bi['C_sum']))
                    if bi['unit_operator_error'] is not None:worst_operator=max(worst_operator,bi['unit_operator_error'])
                    if point!='reference':
                        br=bootstrap[point][name][0][b];bd=decompose(bt,br);bv=response_vectors(bd,f)
                        bp=project_response(bv,bD,bW,bo1,bo2)
                        for j,field in enumerate(PROJECTION_FIELDS):bprojection[b,:,:,j]=bp[field]
                        worst_conservation=max(worst_conservation,bd['conservation_error'])
                row_info=dict(point=point,representation=name,**info);fishers.append(row_info)
                models.append(dict(point=point,representation=name,finite_MC=finite,D=D.tolist(),
                    inverse_covariance=W.tolist(),fixed_operator=op1.tolist() if op1 is not None else None,
                    free_operator=op2.tolist() if op2 is not None else None))
                for j,field in enumerate(FISHER_FIELDS):
                    intervals.append(dict(point=point,representation=name,finite_MC=finite,quantity=field,
                        central=info[field],**uncertainty(binfo[:,j])))
                arrays[key+'_Fisher']=binfo
                if point!='reference':
                    arrays[key+'_projection']=bprojection
                    for c,component in enumerate(COMPONENTS):
                        for j,term in enumerate(TERMS):
                            for k,field in enumerate(PROJECTION_FIELDS):
                                value=projection[field][c,j]
                                row=dict(point=point,representation=name,finite_MC=finite,component=component,term=term,quantity=field,
                                    central=float(value) if np.isfinite(value) else None,**uncertainty(bprojection[:,c,j,k]))
                                shifts.append(row)
                            for mode in ['fixed','free']:
                                for z,value in enumerate(projection[mode+'_residual'][c,j]):
                                    residuals.append(dict(point=point,representation=name,finite_MC=finite,component=component,term=term,
                                        mode=mode,bin=z,delta_probability=float(value) if np.isfinite(value) else None))
                    free_f=projection['free_delta_f'][2,3]
                    row_info['linear_f_outside_physical_range']=bool(np.isfinite(free_f) and not 0<=f+free_f<=1)
                    free_samples=f+bprojection[:,2,3,PROJECTION_FIELDS.index('free_delta_f')]
                    row_info['bootstrap_linear_f_outside_range_N']=int(((free_samples<0)|(free_samples>1)).sum())
                    row_info['bootstrap_free_projection_invalid_N']=int((~np.isfinite(free_samples)).sum())
                print(key,'rank',info['normalized_rank'],'bootstrap_free_invalid',int((~np.isfinite(binfo[:,1])).sum()),flush=True)
    assert worst_C<p['numerical_tolerance'] and worst_operator<p['numerical_tolerance'] and worst_conservation<p['numerical_tolerance']
    save(OUT/'summary.json',dict(Fisher=fishers,protected_counts=protected,source_groups=groups_by_role,
        max_C_normalization_error=worst_C,max_operator_identity_error=worst_operator,max_decomposition_conservation_error=worst_conservation,
        bootstrap_replicates=B,Fisher_bootstrap_fields=FISHER_FIELDS,projection_bootstrap_fields=PROJECTION_FIELDS,
        exact_profiles=0,energy_fits=0,F7_inferences=0))
    save(OUT/'models.json',models)
    scalar_fields=['point','representation','finite_MC','f','regular','normalized_rank','normalized_condition',
        'parameter_correlation','sigma_f_fixed','sigma_f_free','sigma_alpha','sigma_r_over_r_fixed','sigma_r_over_r_free','sigma_f_cost_ratio','C_sum']
    table(OUT/'Fisher.csv',[{key:row[key] for key in scalar_fields} for row in fishers])
    table(OUT/'Fisher_intervals.csv',intervals);table(OUT/'projections.csv',shifts);table(OUT/'residuals.csv',residuals)
    np.savez_compressed(OUT/'bootstrap.npz',**arrays)
    save(OUT/'batch_resources.json',resources(start))


if __name__=='__main__':
    try:main()
    except Exception:
        (OUT/'failure.txt').write_text(traceback.format_exc());raise
