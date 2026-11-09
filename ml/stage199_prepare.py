"""Join every source, split entire parent families, and derive train-only flat weights."""
import collections
import json
import time

import numpy as np

from audited_features import configuration
from latent_transfer_diagnostics import check_x,response
from stage199_common import ROOT,DATA_ROOT,OUT,CACHE,load,save,table,resources,bins


def main():
    tick,cpu=time.perf_counter(),time.process_time()
    p=json.loads((OUT/'protocol.json').read_text());old=load(DATA_ROOT/'ntuples/energy_ml_stage130/new_input.npz')
    fields=['x','incoming','run','eventID','truth_E_GeV','y_lepton','primary_valid','confirmed','raw_charge','status','calo_status']
    parts=[];coverage=[]
    for s in p['sources']:
        if s['mode']=='cache130':
            take=old['source']==s['index'];d={k:old[k][take] for k in fields};d['pz']=old['pz'][take]
            assert take.any(),('Empty original source cache',s['index'])
        else:
            phase='pilot' if s['mode']=='local' and s['index'] in p['pilot_indices'] else 'production'
            path=DATA_ROOT/'ntuples/energy_ml_stage199'/f"{phase}_{s['index']}"
            assert (path/'exitcode.txt').read_text().strip()=='0',path
            z=load(path/'selected.npz');d={k:z[k] for k in fields};d['pz']=z['reco_pz_GeV']
            md=json.loads((path/'summary.json').read_text());assert md['passed']
        n=len(d['x']);check_x(d['x'])
        assert np.all(d['run']==s['run']) and (d['pz']>50).all()
        assert (d['truth_E_GeV']>50).all() and (d['incoming'][:,3]>50000).all()
        np.testing.assert_array_equal(d['x'][:,0],d['pz'].astype('float32'))
        assert len(set(d['eventID']))==n
        start,end=map(int,s['segment'].split('-'))
        assert ((d['eventID']>=start*1000)&(d['eventID']<(end+1)*1000)).all()
        d.update(source=np.full(n,s['index'],np.int32),component=np.full(n,s['component']),
            flux=np.full(n,s['flux']),EVNT=np.full(n,s['EVNT']),origin_mode=np.full(n,s['mode']))
        parts.append(d)
        coverage.append(dict(index=s['index'],run=s['run'],mode=s['mode'],component=s['component'],flux=s['flux'],selected_N=n,
            old_locked=s['old_locked_for_old_studies'],all_rows_included=True))
    d={k:np.concatenate([v[k] for v in parts]) for k in parts[0]}
    # Exactly one chosen response per source/run/event, including old reserved sources.
    ids=np.column_stack([d['run'],d['eventID']]);assert len(np.unique(ids,axis=0))==len(ids)
    incoming,keys=np.unique(d['incoming'].astype('float32'),axis=0,return_inverse=True)
    parent=np.arange(len(incoming))
    def root(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    def join(a,b):
        a,b=root(a),root(b)
        if a!=b:parent[max(a,b)]=min(a,b)
    # Same flux and event ordinal across geometry/crossing-angle variants are
    # conservatively linked; unrelated flux generators sharing an ordinal are not.
    canonical_flux=np.array([str(v).removeprefix('24_xing_angle_wo_caloNu_') for v in d['flux']])
    d['canonical_flux']=canonical_flux
    seen_event={};seen_evnt={}
    for i,(c,e,v) in enumerate(zip(canonical_flux,d['eventID'],d['EVNT'])):
        for table_,token in [(seen_event,(str(c),int(e))),(seen_evnt,(str(v),int(e)))]:
            if token in table_:join(int(keys[i]),table_[token])
            else:table_[token]=int(keys[i])
    roots=np.array([root(i) for i in range(len(incoming))]);family=np.unique(roots,return_inverse=True)[1][keys]
    families,first=np.unique(family,return_index=True);components=d['component'][first]
    rng=np.random.default_rng(p['split']['seed']);assigned=np.zeros(len(families),np.int8)
    for component in sorted(set(components)):
        ix=rng.permutation(np.flatnonzero(components==component));n=len(ix)
        a,b=round(.7*n),round(.85*n);assigned[ix[:a]]=1;assigned[ix[a:b]]=2;assigned[ix[b:]]=3
    role=assigned[family];d.update(role=role,family=family,key_id=keys)
    weight=np.zeros(len(role))
    for r in [1,2,3]:
        ix=role==r;counts=np.bincount(keys[ix],minlength=len(incoming));weight[ix]=1/counts[keys[ix]]
    d['weight']=weight;b=bins(d['truth_E_GeV']);train=role==1
    mass=np.bincount(b[train],weights=weight[train],minlength=8);occupied=mass>0
    factors=np.divide(mass.sum(),occupied.sum()*mass,out=np.zeros(8),where=occupied)
    assert occupied[b].all(),'Unseen train-energy bin; report and freeze handling before any fit'
    d['flat_weight']=weight*factors[b];d['energy_bin']=b
    d.update(response(d['x'],d['raw_charge'],d['status'],d['calo_status']))
    assert np.isclose(d['flat_weight'][train].sum(),weight[train].sum())
    for a,brole in [(1,2),(1,3),(2,3)]:
        for key in ['key_id','family']:
            assert not set(d[key][role==a])&set(d[key][role==brole])
        assert not set(zip(canonical_flux[role==a],d['eventID'][role==a]))&set(zip(canonical_flux[role==brole],d['eventID'][role==brole]))
    rows=[];binrows=[]
    for r,name in [(1,'train'),(2,'cal'),(3,'test')]:
        ix=role==r;w=weight[ix];fw=d['flat_weight'][ix]
        rows.append(dict(role=name,N=int(ix.sum()),families_N=len(np.unique(family[ix])),incoming_N=len(np.unique(keys[ix])),
            sources_N=len(np.unique(d['source'][ix])),K_N=int((d['component'][ix]=='k').sum()),
            base_weight_sum=float(w.sum()),flat_weight_sum=float(fw.sum()),base_ESS=float(w.sum()**2/(w@w)),flat_ESS=float(fw.sum()**2/(fw@fw)),
            flat_weight_min=float(fw.min()),flat_weight_max=float(fw.max())))
        for j in range(8):
            m=ix&(d['energy_bin']==j)
            binrows.append(dict(role=name,bin=j,N=int(m.sum()),incoming_N=len(np.unique(keys[m])),
                base_mass=float(weight[m].sum()),flat_mass=float(d['flat_weight'][m].sum()),train_factor=float(factors[j])))
    CACHE.mkdir(exist_ok=True)
    np.savez_compressed(CACHE/'input.npz',**d)
    np.savez_compressed(CACHE/'split.npz',**{k:d[k] for k in ['run','eventID','source','component','family','key_id','role','weight','flat_weight','energy_bin']})
    table('source_coverage.tsv',coverage);table('split_counts.tsv',rows);table('energy_weights.tsv',binrows)
    save('prepare.json',dict(passed=True,sources_N=len(coverage),records_N=len(role),mode_source_counts=dict(collections.Counter(s['mode'] for s in p['sources'])),
        all_source_records_included=True,no_quarantine=True,features=configuration()['features'],
        train_bin_base_mass=mass.tolist(),train_bin_factors=factors.tolist(),train_flat_bin_mass=np.bincount(d['energy_bin'][train],weights=d['flat_weight'][train],minlength=8).tolist(),
        parent_and_incoming_disjoint=True,source_disjoint=False,target_used_to_assign_roles=False,
        split=rows,overall_independent_confirmation=False,**resources(tick,cpu)))
    print(rows,flush=True)


if __name__=='__main__':main()
