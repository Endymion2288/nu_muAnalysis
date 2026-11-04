"""Stage96 compact all-track input, sparse known-source extraction, no truth targets."""
import argparse
import csv
import json
import multiprocessing as mp
import resource
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

from track_candidate_information import ByteReadCache, TRACK, SCINT, finite

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'workbook/stage96_energy_ml'
CACHE = REPO / 'ntuples/energy_ml_stage96'
SEED = 2026110496
NODE_NAMES = ['pz0_GeV','px0_GeV','py0_GeV','charge','chi2ndof','nLayers','nDoF',
              'x0_mm','y0_mm','z0_mm','x1_mm','y1_mm','z1_mm','module_eta0','module_phi0',
              'station_mask','veto_x_mm','veto_y_mm','timing_x_mm','timing_y_mm','calo_x_mm','calo_y_mm']
EDGE_NAMES = ['delta_x0_y0_mm','delta_calo_mm','delta_veto_mm','delta_slope','same_charge']


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def cost(start):
    return dict(wall_s=time.perf_counter()-start[0], CPU_s=time.process_time()-start[1],
                peak_single_process_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)


def arrays(path):
    with np.load(path) as z:
        return {k:z[k] for k in z.files}


def prepare():
    start=time.perf_counter(),time.process_time()
    CACHE.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True)
    split=arrays(REPO/'ntuples/energy_ml_stage87/split.npz')
    rows=np.flatnonzero(split['role']>0)
    with np.load(REPO/'ntuples/energy_ml_stage94/evaluation_input.npz') as z:
        np.testing.assert_array_equal(z['row'],rows)
        pz=z['pz'].copy();missing=z['input_missing'].copy()
        status_other=missing|z['fit_failure']|z['wave_invalid']|z['calo_invalid']
    manifests={55:list(csv.DictReader((REPO/'ml/configs/low_energy_files.tsv').open(),delimiter='\t'))}
    for stage,path in [(70,'ml/configs/alternative_support_pilot.json'),(81,'workbook/stage81_energy_ml/source_plan.json'),(82,'workbook/stage82_energy_ml/production_protocol.json'),(83,'workbook/stage83_energy_ml/protocol.json')]:
        manifests[stage]=json.loads((REPO/path).read_text())['sources']
    sources=[];mapping={}
    for origin,src in sorted(set(zip(split['origin'][rows].tolist(),split['source'][rows].tolist()))):
        item=manifests[origin][src];path=item.get('input','') if origin not in [70,82] else ''
        mapping[origin,src]=len(sources)
        sources.append(dict(source=f'{origin}:{src}',origin=origin,source_index=src,input=path,
                            file_exists=bool(path and Path(path).is_file()),
                            reason='existing_PHYS' if path else 'temporary_PHYS_deleted'))
    source=np.array([mapping[int(o),int(s)] for o,s in zip(split['origin'][rows],split['source'][rows])],np.int16)
    entries=np.full(len(rows),-1,np.int32);raw=np.empty((len(rows),11));status=np.empty((len(rows),11),np.int32)
    for origin in [55,70,81,82,83]:
        use=np.flatnonzero(split['origin'][rows]==origin);rr=split['origin_row'][rows[use]]
        path='ntuples/energy_ml_stage56/readout.npz' if origin==55 else f'ntuples/energy_ml_stage{origin}/support.npz'
        with np.load(REPO/path) as z:
            idx=np.searchsorted(z['row'],rr) if origin==55 else rr
            if origin==55:np.testing.assert_array_equal(z['row'][idx],rr)
            raw[use]=z['raw_charge'][idx];status[use]=z['status'][idx]
            if origin!=55:entries[use]=z['input_entry'][rr]
    eligible=np.flatnonzero(np.isin(split['role'][rows],[1,2]));rng=np.random.default_rng(SEED)
    chosen=[];seen=set()
    def add(i):
        i=int(i)
        if len(chosen)<40 and int(split['key_id'][rows[i]]) not in seen:
            chosen.append(i);seen.add(int(split['key_id'][rows[i]]))
    for origin in [55,70,81,82,83]:
        use=eligible[split['origin'][rows[eligible]]==origin]
        if len(use):add(use[0])
    for component in ['pi','k','charm']:
        for low in [True,False]:
            use=eligible[(split['component'][rows[eligible]]==component)&((pz[eligible]<100)==low)]
            if len(use):add(use[0])
    for role in [1,2]:
        use=eligible[(split['role'][rows[eligible]]==role)&missing[eligible]]
        for i in use[:2]:add(i)
    # Different known sources, fixed before payload: forty cannot cover all files.
    for s in rng.permutation(np.unique(source[eligible])):
        if any(source[i]==s for i in chosen):continue
        use=eligible[source[eligible]==s];add(use[0])
    for i in eligible:add(i)
    assert len(chosen)==len(seen)==40
    qa=np.isin(np.arange(len(rows)),chosen)
    values={k:split[k][rows] for k in ['key_id','run','eventID','incoming','role','component','origin']}
    values.update(row=rows,source=source,input_entry=entries,pz=pz,raw=raw,status=status,qa=qa,status_other=status_other,input_missing=missing)
    np.savez_compressed(CACHE/'manifest.npz',**values)
    save('sources.json',sources)
    support=[]
    for code in [1,2,3]:
        for comp in ['pi','k','charm']:
            use=(values['role']==code)&(values['component']==comp)
            support.append(dict(role=code,component=comp,N=int(use.sum()),sources=len(np.unique(source[use])),
                                low_pz_N=int((use&(pz<100)).sum()),input_missing_N=int((use&missing).sum()),
                                unavailable_path_N=int(sum(use[i] and not sources[source[i]]['file_exists'] for i in range(len(rows))))))
    save('input_support.json',support)
    save('QA_identities.json',[dict(row=int(rows[i]),key_id=int(values['key_id'][i]),source=sources[source[i]]['source'],role=int(values['role'][i]),component=str(values['component'][i]),pz_GeV=float(pz[i]),input_missing=bool(missing[i])) for i in chosen])
    save('preparation.json',dict(passed=True,records=len(rows),sources=len(sources),available_paths=sum(s['file_exists'] for s in sources),QA_unique_incoming=40,new_PHYS_reads=0,new_fits=0,**cost(start)))
    print(json.dumps(support),flush=True)


def features(arr,present):
    raw={n:np.asarray(ak.to_list(arr['Track_'+n][0]),dtype=float) for n in TRACK if 'Track_'+n in present}
    n=len(raw['pz0'])
    assert all(len(v)==n for v in raw.values()),'track array misalignment'
    v={k:finite(a,positive=k=='pz0',nonnegative=k in ['Chi2','nDoF','nLayers'],
                geometry=k in ['x0','y0','z0','x1','y1','z1'] or k.startswith(('X_at','Y_at'))) for k,a in raw.items()}
    def value(k):return v.get(k,np.full(n,np.nan))
    charge=value('charge').copy();charge[~np.isin(charge,[-1,1])]=np.nan
    eta=value('module_eta0').copy();eta[~np.isin(eta,[-1,1])]=np.nan
    phi=value('module_phi0').copy();phi[~np.isin(phi,[0,1,2,3])]=np.nan
    station=np.column_stack([value('InStation'+str(i)) for i in range(4)])
    valid=np.isin(station,[0,1]).all(1);station_mask=np.where(valid,np.nansum(station*2**np.arange(4),axis=1),np.nan)
    chi=np.divide(value('Chi2'),value('nDoF'),out=np.full(n,np.nan),where=value('nDoF')>0)
    nodes=np.column_stack([value('pz0')/1000,value('px0')/1000,value('py0')/1000,charge,chi,value('nLayers'),value('nDoF'),
        *[value(k) for k in ['x0','y0','z0','x1','y1','z1']],eta,phi,station_mask,
        *[value(k) for k in ['X_atVetoNu','Y_atVetoNu','X_atTrig','Y_atTrig','X_atCalo','Y_atCalo']]])
    order=np.argsort(np.where(np.isfinite(nodes[:,0]),-nodes[:,0],np.inf),kind='stable')
    nodes=nodes[order];edges=[]
    for b in range(1,n):
        a=nodes[0];c=nodes[b]
        def distance(i,j):return float(np.hypot(a[i]-c[i],a[j]-c[j]))
        slope=np.hypot(a[1]/a[0]-c[1]/c[0],a[2]/a[0]-c[2]/c[0])
        same=float(a[3]==c[3]) if np.isfinite([a[3],c[3]]).all() else np.nan
        edges.append([distance(7,8),distance(20,21),distance(16,17),slope,same])
    return nodes,np.asarray(edges,dtype=float).reshape(-1,5)


def read_source(task):
    source,d=task;start=time.perf_counter(),time.process_time();n=len(d['row'])
    available=np.zeros(n,bool);nodes=[np.empty((0,22)) for _ in range(n)];edges=[np.empty((0,5)) for _ in range(n)]
    perf=dict(source=source['source'],N=n,available_N=0,source_read_bytes=0,source_read_calls=0,byte_cache_hits=0,logical_requested_bytes=0,logical_requests=0,reason=source['reason'])
    schema=[];maxdelta=0.;payload_cpu=0.;payload_wall=0.
    if source['file_exists']:
        with ByteReadCache(source['input']) as raw_file,uproot.open(raw_file,array_cache=None,
             decompression_executor=uproot.source.futures.TrivialExecutor(),interpretation_executor=uproot.source.futures.TrivialExecutor()) as f:
            tree=f['nt'];present=set(tree.keys())
            names=['run','eventID']+['Track_'+k for k in TRACK]+['truth_'+k for k in ['pdg','px','py','pz']]+[s+'_'+k for s in SCINT for k in ['raw_charge','status']]
            required=['run','eventID','Track_pz0']+['truth_'+k for k in ['pdg','px','py','pz']]+[s+'_'+k for s in SCINT for k in ['raw_charge','status']]
            schema=[dict(branch=k,present=k in present,typename=tree[k].typename if k in present else 'missing') for k in names]
            missing=sorted(set(required)-present)
            if missing:perf['reason']='required_schema_missing:'+','.join(missing)
            else:
                ids=tree['eventID'].array(library='np');assert len(np.unique(ids))==len(ids)
                lookup={int(e):i for i,e in enumerate(ids)}
                selected=sorted((lookup[int(e)],j) for j,e in enumerate(d['eventID']))
                for entry,j in selected:
                    tick=time.perf_counter(),time.process_time()
                    if d['input_entry'][j]>=0:assert entry==d['input_entry'][j]
                    arr=tree.arrays([k for k in names if k in present],entry_start=entry,entry_stop=entry+1,library='ak')
                    assert int(arr['run'][0])==d['run'][j] and int(arr['eventID'][0])==d['eventID'][j]
                    np.testing.assert_array_equal([ak.to_list(arr['truth_'+k][0])[0] for k in ['pdg','px','py','pz']],d['incoming'][j])
                    np.testing.assert_allclose([float(arr[s+'_raw_charge'][0]) for s in SCINT],d['raw'][j],rtol=0,atol=0,equal_nan=True)
                    np.testing.assert_array_equal([int(arr[s+'_status'][0]) for s in SCINT],d['status'][j])
                    nn,ee=features(arr,present);assert len(nn)>0
                    delta=abs(nn[0,0]-d['pz'][j]);maxdelta=max(maxdelta,float(delta));assert delta<2e-4
                    nodes[j]=nn.astype('float32');edges[j]=ee.astype('float32');available[j]=True
                    payload_cpu+=time.process_time()-tick[1];payload_wall+=time.perf_counter()-tick[0]
                perf.update(available_N=int(available.sum()),reason='complete')
            perf.update(source_read_bytes=raw_file.read_bytes,source_read_calls=raw_file.read_requests,byte_cache_hits=raw_file.hits,
                        logical_requested_bytes=int(f.file.source.num_requested_bytes),logical_requests=int(f.file.source.num_requests))
    counts=np.array([len(a) for a in nodes],np.int32);edgecounts=np.array([len(a) for a in edges],np.int32)
    perf.update(max_leading_pz_difference_GeV=maxdelta,payload_CPU_s=payload_cpu,payload_wall_s=payload_wall,**cost(start))
    print('source',source['source'],'N',n,'available',int(available.sum()),'CPU_s',round(perf['CPU_s'],3),flush=True)
    return dict(row=d['row'],available=available,counts=counts,edgecounts=edgecounts,
                nodes=np.concatenate(nodes),edges=np.concatenate(edges)),perf,dict(source=source['source'],branches=schema)


def extract(qa=False,processes=8):
    start=time.perf_counter(),time.process_time();d=arrays(CACHE/'manifest.npz');sources=json.loads((OUT/'sources.json').read_text())
    selected=np.flatnonzero(d['qa']) if qa else np.arange(len(d['row']))
    if not qa:assert json.loads((OUT/'protocol.json').read_text())['frozen_before_test_payload']
    tasks=[]
    for sid in np.unique(d['source'][selected]):
        ix=selected[d['source'][selected]==sid];tasks.append((sources[sid],{k:v[ix] for k,v in d.items()}))
    if qa:results=[read_source(task) for task in tasks]
    else:
        with mp.get_context('fork').Pool(processes) as pool:results=list(pool.imap_unordered(read_source,tasks,chunksize=1))
    # Flatten source blocks, then reorder incoming rows while keeping complete ragged nodes/edges.
    blocks=[r[0] for r in results];allrows=np.concatenate([b['row'] for b in blocks]);order=np.argsort(allrows)
    counts=np.concatenate([b['counts'] for b in blocks]);ec=np.concatenate([b['edgecounts'] for b in blocks]);allnodes=np.concatenate([b['nodes'] for b in blocks]);alledges=np.concatenate([b['edges'] for b in blocks])
    offsets=np.r_[0,np.cumsum(counts)];eo=np.r_[0,np.cumsum(ec)]
    nodes=np.concatenate([allnodes[offsets[i]:offsets[i+1]] for i in order]);edges=np.concatenate([alledges[eo[i]:eo[i+1]] for i in order])
    available=np.concatenate([b['available'] for b in blocks])[order];counts=counts[order];ec=ec[order];rows=allrows[order]
    np.testing.assert_array_equal(rows,d['row'][selected]);assert np.all(ec==np.maximum(counts-1,0))
    prefix='QA_' if qa else ''
    np.savez_compressed(CACHE/(prefix+'candidates.npz'),row=rows,source=d['source'][selected],available=available,offsets=np.r_[0,np.cumsum(counts)],edge_offsets=np.r_[0,np.cumsum(ec)],nodes=nodes,edges=edges)
    save(prefix+'performance.json',[r[1] for r in results]);save(prefix+'schema.json',[r[2] for r in results])
    child=resource.getrusage(resource.RUSAGE_CHILDREN)
    summary=dict(passed=True,records=len(rows),available_N=int(available.sum()),sources=len(tasks),candidate_nodes=len(nodes),leading_edges=len(edges),
                 processes=1 if qa else processes,source_CPU_s=sum(r[1]['CPU_s'] for r in results),child_CPU_s=child.ru_utime+child.ru_stime,
                 source_read_bytes=sum(r[1]['source_read_bytes'] for r in results),logical_requested_bytes=sum(r[1]['logical_requested_bytes'] for r in results),
                 truth_target_payload_branches=0,new_fits=0,
                 test_requested_records=int((d['role'][selected]==3).sum()),
                 test_available_payload_records=int(((d['role'][selected]==3)&available).sum()),**cost(start))
    save(prefix+'extraction.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','qa','extract']);p.add_argument('--processes',type=int,default=8);a=p.parse_args()
    if a.action=='prepare':prepare()
    else:extract(a.action=='qa',a.processes)
