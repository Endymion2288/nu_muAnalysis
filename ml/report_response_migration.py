#!/usr/bin/env python3
"""Independent event-count/linear algebra checks and stage64 figure."""
import json
import csv
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from response_migration import OUT,REPO,REPRESENTATIONS,TERMS,begin,resources,save
from joint_response import assign,information


def independent_counts(d,p,role,name,weights=None):
    take=d['role']==role;E=d['truth_E_GeV'][take];component=d['component'][take]
    index=d[name][take];low=d['low'][take]
    energy=np.searchsorted(p['truth_E_edges_GeV'],E,side='right')
    h=np.zeros((2,27,p['category_counts'][name]))
    if weights is None:weights=np.ones(len(index))
    for e in range(9):
        for j,production in enumerate(p['production_components']):
            for c in range(2):
                use=(energy==e)&(component==production)&(low==(c==0))
                h[c,e*3+j]=np.bincount(index[use],weights=weights[use],minlength=h.shape[-1])
    return h


def independent_decomposition(t,r):
    # Explicit stratum loop, independent of the batch vectorized implementation.
    result=np.zeros((2,4,t.shape[-1]));T=t.sum(axis=(1,2));R=r.sum(axis=(1,2))
    for c in range(2):
        for k in range(27):
            nt=t[c,k].sum();nr=r[c,k].sum()
            if nt>0 and nr>0:
                result[c,0]+=(nr/R[c]-nt/T[c])*t[c,k]/nt
                result[c,1]+=nr/R[c]*(r[c,k]/nr-t[c,k]/nt)
            else:result[c,2]+=r[c,k]/R[c]-t[c,k]/T[c]
        result[c,3]=r[c].sum(axis=0)/R[c]-t[c].sum(axis=0)/T[c]
    return result


def read_table(name):
    with (OUT/name).open() as stream:return list(csv.DictReader(stream))


def main():
    start=begin();p=json.loads((OUT/'protocol.json').read_text());summary=json.loads((OUT/'summary.json').read_text())
    operators=json.loads((OUT/'operators.json').read_text())
    with np.load(REPO/p['input_cache']) as z:d={k:z[k] for k in z.files}
    with np.load(OUT/'bootstrap.npz') as z:boot={k:z[k] for k in z.files}
    old=json.loads((REPO/'workbook/stage63_energy_ml/protocol_v2.json').read_text())
    for name,index in assign(d['M'],d['S'],old).items():
        if name in REPRESENTATIONS:np.testing.assert_array_equal(index,d[name])
    prior_support=json.loads((REPO/'workbook/stage63_energy_ml/support.json').read_text())
    for row in summary['protected_counts']:
        previous=next(x for x in prior_support if x['role']==row['role'] and x['source']=='pooled')
        for key in row:
            if key!='role':assert row[key]==previous[key],(row['role'],key)
    errors=[];projection_errors=[];operator_errors=[];bootstrap_errors=[];source_weights={}
    # Rebuild the three selected bootstrap draws as per-event weights.
    for role,groups_list in summary['source_groups'].items():
        groups=np.array(groups_list);rng=np.random.default_rng(p['bootstrap_seeds'][role]);draw=np.zeros((500,len(groups)),int)
        for component in ['pi','k','charm']:
            ids=[i for i,g in enumerate(groups_list) if g.startswith(component+':')]
            if ids:draw[:,ids]=rng.multinomial(len(ids),np.full(len(ids),1/len(ids)),size=500)
        gid=np.searchsorted(groups,d['group'][d['role']==role])
        source_weights[role]={bi:draw[bi,gid] for bi in [0,249,499]}
    vector_rows=read_table('vectors.csv')
    for role in ['cal','eval']:
        f=float(d['low'][d['role']==role].mean())
        for name in REPRESENTATIONS:
            t=independent_counts(d,p,'train',name);r=independent_counts(d,p,role,name)
            v=independent_decomposition(t,r);key=role+'_'+name;op=np.array(operators[key]['weights'])
            for row in vector_rows:
                if row['role']==role and row['representation']==name:
                    c=['low','high'].index(row['truth_component']);j=TERMS.index(row['term']);z=int(row['bin'])
                    errors.append(abs(v[c,j,z]-float(row['delta_probability'])))
            mc=t.sum(axis=1);a,b=mc/mc.sum(axis=1)[:,None];q=f*a+(1-f)*b
            V=(np.diag(q)-np.outer(q,q))/1000
            V+=f*f*(np.diag(a)-np.outer(a,a))/mc[0].sum()+(1-f)**2*(np.diag(b)-np.outer(b,b))/mc[1].sum()
            inverse=np.linalg.pinv(V,rcond=1e-12,hermitian=True);other=(a-b)@inverse;other/=other@(a-b)
            operator_errors.append(float(np.max(abs(other-op))))
            np.testing.assert_allclose(operators[key]['sigma_f'],information(mc,f,1000,True),rtol=1e-12)
            for bi in [0,249,499]:
                bt=independent_counts(d,p,'train',name,source_weights['train'][bi])
                br=independent_counts(d,p,role,name,source_weights[role][bi])
                bv=independent_decomposition(bt,br);projected=(bv@op)*np.array([f,1-f])[:,None]
                projected=np.vstack([projected,projected.sum(axis=0)])
                bootstrap_errors.append(float(np.max(abs(projected-boot[key+'_projection'][bi]))))
            pr=(v@op)*np.array([f,1-f])[:,None];pr=np.vstack([pr,pr.sum(axis=0)])
            for row in summary['projections']:
                if row['role']==role and row['representation']==name:
                    c=['low','high','combined'].index(row['truth_component']);j=TERMS.index(row['term'])
                    projection_errors.append(abs(float(row['delta_f'])-pr[c,j]))
    assert max(errors)<1e-12 and max(projection_errors)<1e-12 and max(bootstrap_errors)<1e-12 and max(operator_errors)<1e-10
    # Each signed contribution and source interval; existing profile is a fixed
    # historical comparison, not a new fit or an independently calibrated band.
    fig,axes=plt.subplots(2,2,figsize=(10,6),layout='constrained')
    colors=['#2878b5','#d58230','#777777','#b94043']
    for i,role in enumerate(['cal','eval']):
        for j,name in enumerate(REPRESENTATIONS):
            ax=axes[i,j];rows=[r for r in summary['projections'] if r['role']==role and r['representation']==name and r['truth_component']=='combined']
            for y,(term,color) in enumerate(zip(TERMS,colors)):
                r=next(r for r in rows if r['term']==term)
                ax.hlines(y,100*r['low95'],100*r['high95'],color=color,lw=2)
                ax.plot(100*r['delta_f'],y,'o',color=color)
            exact=next(r for r in summary['linear_checks'] if r['role']==role and r['representation']==name)
            ax.plot(100*exact['existing_profile_delta_f'],4,'D',color='black')
            ax.axvline(0,color='black',lw=.6);ax.set(yticks=np.arange(5),yticklabels=TERMS+['Stage63 profile'],
                xlabel=r'$\Delta f$ [percentage points]',title=f'{role}: {name}')
            ax.invert_yaxis();ax.grid(axis='x',alpha=.15)
    fig.savefig(OUT/'response_migration.png',dpi=160);fig.savefig(OUT/'response_migration.pdf');plt.close(fig)
    # Report every supported conditional layer with source-sign interval status;
    # this is a descriptive input list, not post-hoc removal or a new cut.
    support=read_table('support.csv');priorities=[]
    for row in read_table('stratum_projection.csv'):
        if row['term']!='conditional':continue
        central=float(row['delta_f']);low=float(row['low95']);high=float(row['high95'])
        train=next(x for x in support if x['role']=='train' and x['truth_component']==row['truth_component'] and x['stratum']==row['stratum'])
        held=next(x for x in support if x['role']==row['role'] and x['truth_component']==row['truth_component'] and x['stratum']==row['stratum'])
        if int(train['N'])+int(held['N'])==0:continue
        priorities.append(dict(**row,source_interval_excludes_zero=bool(low>0 or high<0),
            train_N=int(train['N']),train_sources=int(train['sources']),role_N=int(held['N']),role_sources=int(held['sources']),
            train_thin=train['thin_support'],role_thin=held['thin_support']))
    priorities.sort(key=lambda r:abs(float(r['delta_f'])),reverse=True)
    with (OUT/'conditional_support.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(priorities[0]),lineterminator='\n');writer.writeheader();writer.writerows(priorities)
    save(OUT/'validation.json',dict(independent_vector_max_abs_error=max(errors),independent_projection_max_abs_error=max(projection_errors),
        independent_operator_max_abs_error=max(operator_errors),independent_event_bootstrap_max_abs_error=max(bootstrap_errors),
        independently_checked_bootstrap_indices=[0,249,499],all_role_protection_binning_checks_pass=True,
        resources=resources(start)))
    print(json.dumps(dict(linear_checks=summary['linear_checks'],combined_projections=[r for r in summary['projections'] if r['truth_component']=='combined'],
        validation_errors=[max(errors),max(projection_errors),max(operator_errors),max(bootstrap_errors)]),indent=2))


if __name__=='__main__':main()
