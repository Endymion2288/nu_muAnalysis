"""Associate exact sampled HITS parent states with filtered GENIE records."""
import concurrent.futures
import contextlib
import json
import time

import awkward as ak
import numpy as np
import uproot

from stage119_curve_common import ROOT,OUT,CACHE,table


def run(spec,shared=None):
    i,s=spec;start=time.perf_counter();parents=json.loads((OUT/f'pythia_parent_{i}.json').read_text())['parents']
    comp={'pi':'EPOSLHC_pi','k':'EPOSLHC_k','charm':'Powheg_pythia_charm_central'}[s['component']]
    path=f'/eos/experiment/fasernu-data0/MC/Genie_files/genie_output_Pythia6tunes/Pythia6_{s["environment"]}/{comp}/faser_filtered.gfaser.root'
    event=np.array([r['eventID'] for r in parents]);lo=int(event.min());hi=int(event.max())+1
    assert hi-lo==len(parents) and np.array_equal(event,np.arange(lo,hi))
    branches=['vx','vy','vz','n','pdgc','status','firstMother','px','py','pz','E']
    with (uproot.open(path,array_cache=None) if shared is None else contextlib.nullcontext(shared)) as f:
        before=int(f.file.source.num_requested_bytes)
        tree=f['gFaser'];assert hi<=tree.num_entries
        a=ak.to_list(tree.arrays(branches,entry_start=lo,entry_stop=hi));requested=int(f.file.source.num_requested_bytes)-before
    labels=[];mismatch=[]
    for r,g in zip(parents,a):
        n=g['n'];pid=np.asarray(g['pdgc'][:n]);status=np.asarray(g['status'][:n]);mother=np.asarray(g['firstMother'][:n]);e=np.asarray(g['E'][:n]);mom=np.column_stack([g[k][:n] for k in ['px','py','pz']])
        nu=np.flatnonzero((abs(pid)==14)&(status==0));record=dict(source_index=i,input_entry=r['entry'],run=s['run'],eventID=r['eventID'],linked=False,W=np.nan,Q2=np.nan,
            target=0,pre_neutron=np.nan,post_neutron=np.nan,pre_pi0=np.nan,post_pi0=np.nan)
        if len(nu)==1 and 'incoming' in r and 'vertex_mm' in r and 'y' in r:
            ni=nu[0];mu=np.flatnonzero((pid==pid[ni]*13/14)&(mother==ni))
            if len(mu)==1:
                mi=mu[0];incoming=np.array([pid[ni],*list((mom[ni]*1000).astype('float32').astype(float))]);vertex=np.array([g[k]*1000 for k in ['vx','vy','vz']],dtype='float32').astype(float)
                fm=(mom*1000).astype('float32').astype(float);mass2=e*e-np.sum(mom*mom,axis=1);mass=(np.sqrt(np.maximum(mass2,0))*1000).astype('float32').astype(float)
                native_e=np.sqrt(np.sum(fm*fm,axis=1)+mass*mass);y=1-native_e[mi]/native_e[ni]
                exact=np.array_equal(incoming,r['incoming']) and np.array_equal(vertex,r['vertex_mm']) and np.isclose(y,r['y'],rtol=1e-9,atol=1e-10)
                if exact:
                    record['linked']=True;qe=e[ni]-e[mi];qp=mom[ni]-mom[mi];record['Q2']=float(qp@qp-qe*qe)
                    struck=np.flatnonzero((status==11)&np.isin(abs(pid),[2112,2212]))
                    if len(struck)==1:
                        t=struck[0];w2=(e[t]+qe)**2-np.sum((mom[t]+qp)**2)
                        if w2>=0:record['W']=float(np.sqrt(w2))
                    target=pid[(status==0)&(pid>1000000000)]
                    if len(target)==1:record['target']=int(target[0])
                    for prefix,code in [('pre',14),('post',1)]:
                        mask=status==code;mask[mi]=False
                        record[prefix+'_neutron']=int((mask&(pid==2112)).sum());record[prefix+'_pi0']=int((mask&(pid==111)).sum())
                elif len(mismatch)<3:mismatch.append(dict(entry=r['entry'],eventID=r['eventID'],max_incoming_abs_MeV=float(np.max(abs(incoming-r['incoming']))),max_vertex_abs_mm=float(np.max(abs(vertex-r['vertex_mm']))),y_delta=float(y-r['y'])))
        labels.append(record)
    return labels,dict(index=i,run=s['run'],input=path,parents=len(parents),linked_N=sum(r['linked'] for r in labels),requested_bytes=requested,
        wall_s=time.perf_counter()-start,first_mismatches=mismatch,certification='event number proposed as filtered generator entry, accepted only after actual incoming + vertex + primary y match; no row-only association')


def group_run(group):
    s=group[0][1];comp={'pi':'EPOSLHC_pi','k':'EPOSLHC_k','charm':'Powheg_pythia_charm_central'}[s['component']]
    path=f'/eos/experiment/fasernu-data0/MC/Genie_files/genie_output_Pythia6tunes/Pythia6_{s["environment"]}/{comp}/faser_filtered.gfaser.root'
    with uproot.open(path,array_cache=None) as f:
        initial=int(f.file.source.num_requested_bytes);result=[run(item,f) for item in group]
        result[0][1]['requested_bytes']+=initial
    return result


def main():
    CACHE.mkdir(parents=True,exist_ok=True)
    p=json.loads((OUT/'pythia_contract.json').read_text());tick=time.perf_counter()
    groups=[[item for item in enumerate(p['sources']) if item[1]['run']==run] for run in sorted({s['run'] for s in p['sources']})]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:r=sum(list(pool.map(group_run,groups)),[])
    records=sum((v[0] for v in r),[]);arrays={k:np.asarray([v[k] for v in records]) for k in records[0]}
    np.savez_compressed(CACHE/'genie_labels.npz',**arrays)
    info=dict(sources=[v[1] for v in r],wall_s=time.perf_counter()-tick,requested_bytes=sum(v[1]['requested_bytes'] for v in r),
        matches=sum(v[1]['linked_N'] for v in r),parents=len(records),tolerances='exact incoming and vertex after documented McEventCollection_p6 Float_t persistence; primary y reconstructed from persisted momentum/mass, atol1e-10/rtol1e-9',
        diagnostic_only='W/Q2/status composition never deployment features; no interaction-channel claim without GHEP summary')
    (OUT/'genie_link.json').write_text(json.dumps(info,indent=2)+'\n');print(info,flush=True)
    assert info['requested_bytes']<300000000


if __name__=='__main__':main()
