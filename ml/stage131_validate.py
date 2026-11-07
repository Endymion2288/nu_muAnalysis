"""Independent row-space weighted risks, role/feature and oracle-domain checks."""
import csv
import json
import math
import numpy as np
from audited_features import configuration
from latent_transfer_diagnostics import check_x
from stage131_common import OUT,CACHE,ART,load,table,evaluation_masks

def main():
    d=load(CACHE/'matched_input.npz');pred=load(ART/'energy_predictions.npz');boots=load(CACHE/'bootstrap_draws.npz');check_x(d['x']);rules=configuration()['rules'];names=configuration()['features'];audits=[]
    assert set(d['role'])=={1,2,3} and np.all(d['pz']>50)
    assert len(np.unique(d['incoming'].astype('float32'),axis=0))==len(d['role'])
    for j,n in enumerate(names):
        v=d['x'][:,j];r=rules[n];finite=np.isfinite(v)
        sentinel=int(np.isin(v,r.get('sentinels',[])).sum());invalid=int((finite&((v<=0) if r['domain']=='positive' else (v<0))).sum()) if r['domain'] in ['positive','nonnegative','count'] else 0
        assert sentinel==invalid==int(np.isinf(v).sum())==0
        audits.append(dict(feature=n,domain=r['domain'],finite_N=int(finite.sum()),NaN_N=int((~finite).sum()),negative_N=int((v<0).sum()),minus1_N=int((v==-1).sum()),finite_sentinel_N=sentinel,domain_violation_N=invalid))
    table('feature_domain_audit.tsv',audits)
    assert np.isfinite(d['total']).all() and (d['total']>=0).all()
    f=d['lineage'][np.isfinite(d['lineage'])];assert ((f>=0)&(f<=1)).all()
    matrices=load(CACHE/'fit_matrices.npz');np.testing.assert_array_equal(matrices['P'][:,:62],d['x'])
    assert matrices['P'].shape[1]==67 and np.isfinite(matrices['P'][:,62:]).all()
    for arm in matrices:assert not np.isinf(matrices[arm]).any()
    assert not set(names)&{'ML_mu_p_GeV','ML_track_p1_GeV','ML_track_pz1_GeV','ML_track_log_p1_over_p0'}
    rows=list(csv.DictReader((OUT/'paired.tsv').open(),delimiter='\t'));checks=[];maximum=0.;scalars=0
    for role in [2,3]:
        ix=np.flatnonzero(d['role']==role);draw=boots[f'role{role}'];sd={k:v[ix] for k,v in d.items()};layers=evaluation_masks(sd)
        contrasts=list(dict.fromkeys((r['candidate'],r['reference']) for r in rows if int(r['role'])==role))
        for candidate,reference in contrasts:
            for layer in layers:
                mask=layers[layer];indices=ix[mask]
                if not len(indices):continue
                r=next(x for x in rows if int(x['role'])==role and x['candidate']==candidate and x['reference']==reference and x['stratum']==layer)
                w=d['weight'][indices];a=pred[candidate][indices]-np.log(d['truth_E_GeV'][indices]);b=pred[reference][indices]-np.log(d['truth_E_GeV'][indices]);relA=np.expm1(a);relB=np.expm1(b)
                central=math.sqrt(math.fsum(float(v*e*e) for v,e in zip(w,a))/math.fsum(float(v*e*e) for v,e in zip(w,b)))
                err=abs(central-float(r['RMSE_ratio']));n=1;ratios=[];tails={s:[] for s in ['total','positive','negative']}
                flags={'total':(abs(relA)>.5,abs(relB)>.5),'positive':(relA>.5,relB>.5),'negative':(relA<-.5,relB<-.5)}
                for sign,(fa,fb) in flags.items():
                    independent=100*math.fsum(float(wi)*(int(ai)-int(bi)) for wi,ai,bi in zip(w,fa,fb))/math.fsum(map(float,w))
                    err=max(err,abs(independent-float(r[sign+'_tail_delta_pp'])));n+=1
                for resample in draw[:,mask]:
                    # Reconstruct the actual resampled row list, independent of
                    # evaluation's count-matrix multiplication.
                    pos=np.repeat(np.arange(len(indices)),resample)
                    if not len(pos):continue
                    wa=w[pos];aa=np.average(a[pos]**2,weights=wa);bb=np.average(b[pos]**2,weights=wa)
                    if bb<=0:continue
                    ratios.append(np.sqrt(aa/bb))
                    for sign,(fa,fb) in flags.items():tails[sign].append(100*np.average(fa[pos].astype(float)-fb[pos].astype(float),weights=wa))
                if len(ratios)>=475:
                    actual=np.quantile(ratios,[.025,.975]);err=max(err,abs(actual[0]-float(r['low95'])),abs(actual[1]-float(r['high95'])));n+=2
                    for sign,values in tails.items():
                        actual=np.quantile(values,[.025,.975]);err=max(err,abs(actual[0]-float(r[sign+'_tail_low95_pp'])),abs(actual[1]-float(r[sign+'_tail_high95_pp'])));n+=2
                assert err<1e-10,(role,candidate,reference,layer,err)
                maximum=max(maximum,err);scalars+=n;checks.append(dict(role=role,candidate=candidate,reference=reference,stratum=layer,N=len(indices),independent_scalars=n,max_abs_difference=err))
    table('independent_validation.tsv',checks)
    result=dict(passed=True,independently_reconstructed_scalars=scalars,max_abs_difference=maximum,pz0_raw11_typedNaN_signed_Calo_missing=True,proxy_contains_no_oracleavailability=True,roles_disjoint=True,reserve_forward=0,point_and_intervals='independent fsum and explicit resampled rows vs matrix products',scope='numerical/structural verification,not fullgenerator-family independence or detector/systematiccertification')
    (OUT/'independent_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(result)

if __name__=='__main__':main()
