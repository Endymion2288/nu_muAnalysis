"""Fixed X/availability/sigma/content/shuffled-content energy comparison."""
import json
from pathlib import Path
import numpy as np
import stage129_energy as energy
from stage191_review import read, validate
from stage191_summary import A_NAMES,V_NAMES,C_NAMES

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage191_energy_ml'
CACHE=ROOT/'ntuples/energy_ml_stage191';ART=ROOT/'ml/artifacts/stage191'
energy.OUT,energy.ART=OUT,ART
load,table=energy.load,energy.table


def write(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def inputs(save=False):
    p=json.loads((OUT/'protocol.json').read_text());d=load(ROOT/'ntuples/energy_ml_stage119/old_input.npz')
    n=len(d['role']);active=d['role']>0
    assert n==89033 and int(active.sum())==71376
    a=np.full((n,4),np.nan,'float32');v=np.full((n,3),np.nan,'float32');c=np.full((n,12),np.nan,'float32')
    loaded=np.zeros(n,bool);source=np.full(n,-1,int)
    pilot={r['case']['row']:r for r in read('pilot_0')['records']};overlap=0;audits=[];failures=[];reason_counts={};reference_qa=[]
    for group in range(35):
        data=read(f'full_{group}')
        if save:audits.append(dict(group=group,**validate(data,d)))
        for meta in data['metadata']:
            if meta.get('PHYS_reference'):
                reference_qa.append(dict(source_index=int(meta['label']),note=meta['PHYS_reference'],N=meta['requested_N']))
            for difference in meta.get('legacy_PHYS_pz_differences',[]):
                reference_qa.append(dict(source_index=int(meta['label']),note='Legacy PHYS differs; frozen original cached reference retained',**difference))
        for r in data['records']:
            case=r['case'];i=case['row'];assert active[i] and not loaded[i]
            assert case['role']==d['role'][i] and (case['run'],case['event'])==(d['run'][i],d['eventID'][i])
            loaded[i]=True;source[i]=case['source_index']
            a[i]=r['summary']['availability'];v[i]=r['summary']['sigma'];c[i]=r['summary']['content']
            key=(case['source_index'],case['role'],r['original_leading_match'],r['reason'])
            reason_counts[key]=reason_counts.get(key,0)+1
            if not r['original_leading_match'] or not r['start_supported']:
                failures.append(dict(row=i,source_index=case['source_index'],role=case['role'],run=case['run'],event=case['event'],
                    original_leading_matched=r['original_leading_match'],reason=r['reason']))
            if i in pilot:
                q=pilot[i];assert r['summary']==q['summary'] and r['original_leading_match']==q['original_leading_match']
                overlap+=1
    np.testing.assert_array_equal(loaded,active);assert overlap==len(pilot)
    assert np.isnan(a[~active]).all() and np.isnan(v[~active]).all() and np.isnan(c[~active]).all()
    names=energy.configuration()['features'];arrays=dict(X=d['x'])
    arrays['A']=np.column_stack([d['x'],a]).astype('float32')
    arrays['V']=np.column_stack([arrays['A'],v]).astype('float32')
    arrays['C']=np.column_stack([arrays['V'],c]).astype('float32')
    qi=[names.index(q) for q in p['conditioning_charge_columns']]
    total=np.sum(d['x'][:,qi].astype(float),axis=1)
    activity=np.arcsinh(total)
    pzbin=np.digitize(d['pz'],p['pz_edges_GeV'])
    qbin=np.digitize(np.where(np.isfinite(activity),activity,np.inf),p['activity_edges'])
    sigmabin=np.digitize(np.where(np.isfinite(v),np.exp(v.astype(float)),np.inf),p['sigma_edges_mm'])
    buckets={}
    for i in np.flatnonzero(active):
        key=(int(d['role'][i]),str(d['component'][i]),int(pzbin[i]),int(qbin[i]),*map(int,a[i]),*map(int,sigmabin[i]))
        buckets.setdefault(key,[]).append(i)
    permutation=np.arange(n);rng=np.random.default_rng(p['shuffle_seed'])
    for key in sorted(buckets):
        ix=np.asarray(buckets[key]);permutation[ix]=rng.permutation(ix)
    np.testing.assert_array_equal(np.isfinite(c[permutation]),np.isfinite(c))
    arrays['S']=np.column_stack([arrays['V'],c[permutation]]).astype('float32')
    labels=dict(X=names,A=names+A_NAMES,V=names+A_NAMES+V_NAMES,C=names+A_NAMES+V_NAMES+C_NAMES,
        S=names+A_NAMES+V_NAMES+[q+'_shuffled' for q in C_NAMES])
    if save:
        np.savez_compressed(CACHE/'control.npz',availability=a,sigma=v,content=c,permutation=permutation,source_index=source)
        write('preparation.json',dict(passed=True,loaded_N=int(loaded.sum()),pilot_full_exact_N=overlap,
            raw_source_audits=audits,quarantine_native_read_N=0,reserved_native_read_N=0))
        rows=[]
        for role in [1,2,3]:
            for layer,mask in energy.masks(d).items():
                ix=np.flatnonzero((d['role']==role)&mask)
                rows.append(dict(role=role,stratum=layer,N=len(ix),matched_start_N=int((a[ix,0]>0).sum()),
                    any_valid_layer_N=int(np.any(a[ix,1:]>0,axis=1).sum()),all_valid_layers_N=int(np.all(a[ix,1:]>0,axis=1).sum()),
                    moved_rows_N=int((permutation[ix]!=ix).sum())))
        table('content_support.tsv',rows)
        table('native_identity_exceptions.tsv',failures)
        table('reference_source_qa.tsv',reference_qa)
        table('native_reason_support.tsv',[dict(source_index=k[0],role=k[1],matched=k[2],reason=k[3],N=n) for k,n in sorted(reason_counts.items())])
    return d,arrays,labels
