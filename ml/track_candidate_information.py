"""Stage95: frozen train/cal track candidates, geometry relations and truth diagnostics."""
import argparse
import csv
from collections import OrderedDict
import json
import math
import multiprocessing as mp
import resource
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'workbook/stage95_energy_ml'
CACHE = REPO / 'ntuples/energy_ml_stage95'
SEED = 2026110495
SCINT = ['VetoNu0', 'VetoNu1', 'Veto10', 'Veto20', 'Veto21'] + [f'Timing{i}' for i in range(4)] + ['Preshower0', 'Preshower1']
TRACK = ['pz0','px0','py0','x0','y0','z0','x1','y1','z1','charge','Chi2','nDoF','nLayers','module_eta0','module_phi0','InStation0','InStation1','InStation2','InStation3','X_atVetoNu','Y_atVetoNu','X_atTrig','Y_atTrig','X_atCalo','Y_atCalo']
TRUTH = ['pdg','barcode','px','py','pz','m','prod_x','prod_y','prod_z','dec_x','dec_y','dec_z']
MATCH = ['t_pdg','t_barcode','t_pdg_parent','t_barcode_parent','t_truthHitRatio']


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def table(name, rows):
    with (OUT / name).open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter='\t', lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def load(path, names=None):
    with np.load(REPO / path) as z:
        return {k: z[k] for k in (names if names is not None else z.files)}


def cost(start):
    return dict(wall_s=time.perf_counter()-start[0], CPU_s=time.process_time()-start[1], peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)


def prepare():
    start=time.perf_counter(),time.process_time();OUT.mkdir(parents=True, exist_ok=True);CACHE.mkdir(parents=True, exist_ok=True)
    split=load('ntuples/energy_ml_stage87/split.npz')
    meta=load('ntuples/energy_ml_stage94/evaluation_input.npz', ['row','pz','input_missing','fit_failure','wave_invalid','calo_invalid'])
    ii=np.searchsorted(meta['row'],np.flatnonzero(np.isin(split['role'],[1,2])))
    rows=meta['row'][ii]; assert np.isin(split['role'][rows],[1,2]).all()
    manifests={55:list(csv.DictReader((REPO/'ml/configs/low_energy_files.tsv').open(),delimiter='\t'))}
    for stage,path in [(70,'ml/configs/alternative_support_pilot.json'),(81,'workbook/stage81_energy_ml/source_plan.json'),(82,'workbook/stage82_energy_ml/production_protocol.json'),(83,'workbook/stage83_energy_ml/protocol.json')]:
        manifests[stage]=json.loads((REPO/path).read_text())['sources']
    sources={};records=[];entries={}
    for stage in [70,81,82,83]:entries[stage]=load(f'ntuples/energy_ml_stage{stage}/support.npz',['input_entry'])['input_entry']
    for j,row in enumerate(rows):
        origin=int(split['origin'][row]);src=int(split['source'][row]);sid=f'{origin}:{src}'
        if sid not in sources:
            item=manifests[origin][src];path=item.get('input','') if origin not in [70,82] else ''
            sources[sid]=dict(source=sid,origin=origin,source_index=src,component=str(split['component'][row]),group=str(split['group'][row]),role=int(split['role'][row]),input=path,availability='existing_PHYS' if path else 'temporary_produced_PHYS_not_retained',file_exists=bool(path and Path(path).is_file()))
        records.append(dict(row=int(row),key_id=int(split['key_id'][row]),origin=origin,origin_row=int(split['origin_row'][row]),source=sid,role=int(split['role'][row]),component=str(split['component'][row]),group=str(split['group'][row]),run=int(split['run'][row]),eventID=int(split['eventID'][row]),input_entry=-1 if origin==55 else int(entries[origin][split['origin_row'][row]]),pz_GeV=float(meta['pz'][ii[j]]),status_other=bool(any(meta[k][ii[j]] for k in ['input_missing','fit_failure','wave_invalid','calo_invalid'])),input_missing=bool(meta['input_missing'][ii[j]]),incoming=split['incoming'][row].tolist()))
    # Choose at most eight source views per component, before opening ROOT or new diagnostics.
    rng=np.random.default_rng(SEED);chosen=[]
    for comp in ['pi','k','charm']:
        pool=[s for s,v in sources.items() if v['component']==comp];order=list(rng.permutation(sorted(pool)))
        forced=[]
        for origin in [70,81,82,83]:
            candidates=[s for s in order if sources[s]['origin']==origin]
            if candidates:forced.append(candidates[0])
        for role in [2,1]:
            candidates=[s for s in order if sources[s]['role']==role and s not in forced]
            forced.extend(candidates[:2])
        chosen.extend(list(dict.fromkeys(forced+order))[:8])
    eligible=[r for r in records if r['source'] in chosen]
    buckets={}
    for r in eligible:
        key=(r['source'],r['pz_GeV']<100,r['status_other']);buckets.setdefault(key,[]).append(r)
    for key in buckets:
        r=buckets[key];buckets[key]=[r[i] for i in rng.permutation(len(r))]
    cohort=[];seen=set();keys=sorted(buckets)
    while len(cohort)<2048:
        progress=False
        for key in keys:
            while buckets[key] and buckets[key][-1]['key_id'] in seen:buckets[key].pop()
            if not buckets[key]:continue
            r=buckets[key].pop();cohort.append(r);seen.add(r['key_id']);progress=True
            if len(cohort)==2048:break
        if not progress:raise RuntimeError('Insufficient fixed-source distinct incoming support')
    # QA covers source and X-status buckets, then fills to40; no Y/risk use.
    qa=[];qseen=set()
    def add(record):
        if record['row'] not in qseen and len(qa)<40:
            qa.append(record);qseen.add(record['row'])
    for comp in ['pi','k','charm']:
        add(next(r for r in cohort if r['component']==comp))
    for origin in [55,70,81,82,83]:
        rr=[r for r in cohort if r['origin']==origin]
        if rr:add(rr[0])
    for r in cohort:
        if r['input_missing']:add(r)
    for source in sorted({r['source'] for r in cohort}):
        add(next(r for r in cohort if r['source']==source))
    for key in sorted({(r['source'],r['status_other'],r['pz_GeV']<100) for r in cohort}):
        add(next(r for r in cohort if (r['source'],r['status_other'],r['pz_GeV']<100)==key))
    for r in cohort:add(r)
    assert len(qa)==len({r['key_id'] for r in qa})==40
    for r in cohort:r['qa']=r['row'] in qseen
    references={55:load('ntuples/energy_ml_stage56/readout.npz',['row','raw_charge','status'])}
    for origin in [70,81,82,83]:references[origin]=load(f'ntuples/energy_ml_stage{origin}/support.npz',['raw_charge','status'])
    diagnostics=load('ntuples/energy_ml_stage94/evaluation_input.npz',['row','truth_E_GeV','y_lepton','confirmed'])
    for r in cohort:
        reference=references[r['origin']];j=r['origin_row']
        if r['origin']==55:
            j=int(np.searchsorted(reference['row'],j));assert reference['row'][j]==r['origin_row']
        r['reference_raw_charge']=reference['raw_charge'][j].tolist();r['reference_status']=reference['status'][j].astype(int).tolist()
        k=int(np.searchsorted(diagnostics['row'],r['row']));assert diagnostics['row'][k]==r['row']
        r['reference_truth_E_GeV']=float(diagnostics['truth_E_GeV'][k]);r['reference_y_lepton']=float(diagnostics['y_lepton'][k]);r['reference_confirmed']=bool(diagnostics['confirmed'][k])
    used={r['source'] for r in cohort};source_list=[sources[s] for s in sorted(used)]
    (CACHE/'cohort.json').write_text(json.dumps(dict(seed=SEED,N=2048,unique_incoming=2048,records=cohort,sources=source_list,selection='component<=8 sources, force represented enrichment origins and train/cal; deterministic X/source/status round-robin and one view per incoming; no truth/prediction selection',target='diagnostic enriched cohort, NOT natural flux or full-pool prevalence',test_payload=False),ensure_ascii=False,indent=2)+'\n')
    table('sources.tsv',source_list)
    counts=[]
    for label,rr in [('cohort',cohort),('QA',[r for r in cohort if r['qa']])]:
        for comp in ['pi','k','charm']:
            a=[r for r in rr if r['component']==comp];counts.append(dict(scope=label,component=comp,N=len(a),sources=len({r['source'] for r in a}),train=sum(r['role']==1 for r in a),cal=sum(r['role']==2 for r in a),low_pz=sum(r['pz_GeV']<100 for r in a),status_other=sum(r['status_other'] for r in a),missing=sum(r['input_missing'] for r in a)))
    table('cohort_support.tsv',counts);save('preparation.json',dict(passed=True,source_count=len(source_list),unavailable_sources=[s['source'] for s in source_list if not s['file_exists']],new_ROOT_reads=0,new_fits=0,**cost(start)))
    print(json.dumps(counts),flush=True)


def finite(v, positive=False, nonnegative=False, geometry=False):
    v=np.asarray(v,dtype=float).copy();bad=~np.isfinite(v)|(abs(v)==999999)
    if geometry:bad|=v==-999
    if positive:bad|=v<=0
    if nonnegative:bad|=v<0
    v[bad]=np.nan;return v


def analyze(arr, record, present):
    """All track rows retained; candidate list has no momentum/quality rejection."""
    raw={n:np.asarray(ak.to_list(arr['Track_'+n][0])) for n in TRACK if 'Track_'+n in present}
    n=len(raw['pz0']);assert n>0
    for name,v in raw.items():assert len(v)==n,(record['source'],record['eventID'],name,len(v),n)
    v={name:finite(a,positive=name=='pz0',nonnegative=name in ['Chi2','nDoF','nLayers'],geometry=name in ['x0','y0','z0','x1','y1','z1'] or name.startswith(('X_at','Y_at'))) for name,a in raw.items()}
    v['charge'][~np.isin(v['charge'],[-1,1])]=np.nan
    for key,allowed in [('module_eta0',[-1,1]),('module_phi0',[0,1,2,3])]:
        if key in v:v[key][~np.isin(v[key],allowed)]=np.nan
    lead=int(np.nanargmax(v['pz0']));assert abs(v['pz0'][lead]/1000-record['pz_GeV'])<2e-4
    assert int(arr['run'][0])==record['run'] and int(arr['eventID'][0])==record['eventID']
    raw_truth={name:np.asarray(ak.to_list(arr['truth_'+name][0]),dtype=float) for name in TRUTH}
    nt=len(raw_truth['pdg']);assert nt>0 and all(len(x)==nt for x in raw_truth.values())
    incoming=[raw_truth['pdg'][0]]+[raw_truth[a][0] for a in ['px','py','pz']]
    np.testing.assert_array_equal(incoming,record['incoming'])
    primary=(raw_truth['pdg']==raw_truth['pdg'][0]*13/14)
    for axis in ['x','y','z']:primary &= abs(raw_truth['prod_'+axis]-raw_truth['dec_'+axis][0])<=.0001
    assert primary.sum()==1;ip=int(np.flatnonzero(primary)[0])
    match={name:np.asarray(ak.to_list(arr[name][0])) for name in MATCH if name in present}
    assert all(len(a)==n for a in match.values())
    confirm=(match['t_pdg']==raw_truth['pdg'][ip])&(match['t_barcode']==raw_truth['barcode'][ip])&(match['t_pdg_parent']==raw_truth['pdg'][0])&(match['t_barcode_parent']==raw_truth['barcode'][0])
    E=math.sqrt(sum(raw_truth[k][0]**2 for k in ['px','py','pz','m']))/1000
    muE=math.sqrt(sum(raw_truth[k][ip]**2 for k in ['px','py','pz','m']))/1000
    truth_pz=raw_truth['pz'][ip]/1000
    np.testing.assert_allclose([E,1-muE/E],[record['reference_truth_E_GeV'],record['reference_y_lepton']],rtol=1e-10,atol=1e-12)
    assert bool(confirm[lead])==record['reference_confirmed']
    hit=np.asarray(ak.to_list(arr['Track_hitSet'][0])) if 'Track_hitSet' in present else np.array([],int)
    # Source shows hitSet is layer-side bitmask pushed BEFORE saved-track rejection.
    # Even equal lengths do not turn it into cluster IDs. Never infer shared-hit edges.
    stations=np.column_stack([v['InStation'+str(i)] for i in range(4)]) if all('InStation'+str(i) in v for i in range(4)) else np.full((n,4),np.nan)
    eta=v.get('module_eta0',np.full(n,np.nan));phi=v.get('module_phi0',np.full(n,np.nan))
    station_valid=np.isin(stations,[0,1]).all(1)
    rows=[]
    for j in range(n):
        def value(name,scale=1.):return float(v[name][j]/scale) if name in v else float('nan')
        ndof=value('nDoF');chi=value('Chi2')
        rows.append(dict(row=record['row'],track_index=j,leading=j==lead,pz0_GeV=value('pz0',1000),px0_GeV=value('px0',1000),py0_GeV=value('py0',1000),charge=value('charge'),chi2ndof=chi/ndof if ndof>0 else float('nan'),nLayers=value('nLayers'),nDoF=ndof,
             x0_mm=value('x0'),y0_mm=value('y0'),z0_mm=value('z0'),x1_mm=value('x1'),y1_mm=value('y1'),z1_mm=value('z1'),module_eta0=value('module_eta0'),module_phi0=value('module_phi0'),station_mask=sum(int(stations[j,i])<<i for i in range(4)) if station_valid[j] else float('nan'),
             veto_x_mm=value('X_atVetoNu'),veto_y_mm=value('Y_atVetoNu'),timing_x_mm=value('X_atTrig'),timing_y_mm=value('Y_atTrig'),calo_x_mm=value('X_atCalo'),calo_y_mm=value('Y_atCalo')))
    edges=[];distinct=0;near=0
    for a in range(n):
        for b in range(a+1,n):
            def dist(x,y):
                return float(np.hypot(v[x][a]-v[x][b],v[y][a]-v[y][b])) if x in v and y in v else float('nan')
            d0=dist('x0','y0');dc=dist('X_atCalo','Y_atCalo');dv=dist('X_atVetoNu','Y_atVetoNu')
            # Fixed1mm is only a named geometric proximity diagnostic, not shared-hit identity.
            near+=int(np.isfinite(d0) and np.isfinite(dc) and d0<1 and dc<1)
            distinct+=int(np.isfinite(dc) and dc>=1)
            slopes=[v[k]/v['pz0'] if k in v else np.full(n,np.nan) for k in ['px0','py0']]
            angle=float(np.hypot(*(s[a]-s[b] for s in slopes)))
            edges.append(dict(row=record['row'],track_i=a,track_j=b,delta_x0_y0_mm=d0,delta_calo_mm=dc,delta_veto_mm=dv,delta_slope=angle,same_charge=bool(v['charge'][a]==v['charge'][b]) if np.isfinite(v['charge'][[a,b]]).all() else float('nan')))
    bad_raw=0;negative_raw=0
    for j,det in enumerate(SCINT):
        np.testing.assert_allclose(float(arr[det+'_raw_charge'][0]),record['reference_raw_charge'][j],rtol=0,atol=0,equal_nan=True)
        assert int(arr[det+'_status'][0])==record['reference_status'][j]
        charge=float(arr[det+'_raw_charge'][0]);status=int(arr[det+'_status'][0]);bad=not np.isfinite(charge) or bool(status&(8|128|256));bad_raw+=bad;negative_raw+=int(charge<0 and not bad)
    validpz=np.isfinite(v['pz0']);primary_candidates=confirm&validpz
    # Physically meaningful diagnostic: muon longitudinal momentum, never nu energy oracle.
    leaderr=math.log(v['pz0'][lead]/1000/truth_pz) if truth_pz>0 else float('nan')
    oracle=min((abs(math.log(q/1000/truth_pz)) for q in v['pz0'][primary_candidates]),default=float('nan')) if truth_pz>0 else float('nan')
    event=dict(row=record['row'],available=True,n_tracks=n,n_valid_pz=int(validpz.sum()),lead_index=lead,n_pairs=len(edges),finite_calo_tracks=sum(np.isfinite(r['calo_x_mm']) and np.isfinite(r['calo_y_mm']) for r in rows),finite_veto_tracks=sum(np.isfinite(r['veto_x_mm']) and np.isfinite(r['veto_y_mm']) for r in rows),finite_timing_tracks=sum(np.isfinite(r['timing_x_mm']) and np.isfinite(r['timing_y_mm']) for r in rows),valid_station_tracks=int(station_valid.sum()),three_downstream_tracks=int((station_valid&(stations[:,1:]==1).all(1)).sum()),invalid_module_tracks=int((~np.isin(eta,[-1,1])|~np.isin(phi,[0,1,2,3])).sum()),hitset_length=len(hit),hitset_aligned=len(hit)==n,hitset_24bit=bool(((hit>=0)&(hit<2**24)).all()),geometric_near_pairs=near,distinct_calo_pairs=distinct,raw_invalid_channels=bad_raw,valid_negative_raw_channels=negative_raw,truth_E_GeV=E,y_lepton=1-muE/E,lead_primary_confirmed=bool(confirm[lead]),any_primary_confirmed=bool(confirm.any()),primary_confirmed_tracks=int(confirm.sum()),primary_truth_pz_GeV=truth_pz,lead_mu_log_error=leaderr,matched_candidate_oracle_abs_log_error=oracle,truth_hitratio_finite_tracks=int(np.isfinite(match.get('t_truthHitRatio',np.full(n,np.nan))).sum()),truth_hitratio_out_of_range=int(((match.get('t_truthHitRatio',np.full(n,np.nan))<0)|(match.get('t_truthHitRatio',np.full(n,np.nan))>1)).sum()))
    labels=[dict(row=record['row'],track_index=j,primary_confirmed=bool(confirm[j]),truth_hit_ratio=float(match['t_truthHitRatio'][j]) if 't_truthHitRatio' in match else float('nan')) for j in range(n)]
    return event,rows,edges,labels


class ByteReadCache:
    """Bounded exact-range byte reuse; sparse entry selection never expands payload."""
    def __init__(self,path,limit=64*1024*1024):
        self.stream=open(path,'rb');self.limit=limit;self.cache=OrderedDict();self.size=0
        self.read_bytes=0;self.read_requests=0;self.hits=0
    def seek(self,*args):return self.stream.seek(*args)
    def tell(self):return self.stream.tell()
    def read(self,n=-1):
        key=(self.tell(),n)
        if key in self.cache:
            data=self.cache.pop(key);self.cache[key]=data;self.stream.seek(key[0]+len(data));self.hits+=1;return data
        data=self.stream.read(n);self.read_bytes+=len(data);self.read_requests+=1
        if len(data)<=self.limit:
            while self.cache and self.size+len(data)>self.limit:
                _,old=self.cache.popitem(last=False);self.size-=len(old)
            self.cache[key]=data;self.size+=len(data)
        return data
    def __enter__(self):return self
    def __exit__(self,*args):self.stream.close()


def read_source(task):
    source,records=task;start=time.perf_counter(),time.process_time();sid=source['source']
    if not source['file_exists']:
        return dict(source=sid,available=False,requested_bytes=0,requested_requests=0,payload_records=0,identity_branch_entries=0,raw_entries=0,branch_count=0,source_read_bytes=0,source_read_requests=0,byte_cache_hits=0,reason=source['availability'],**cost(start)),[dict(row=r['row'],available=False) for r in records],[],[],[],[]
    result=[];tracks=[];edges=[];labels=[];schemas=[]
    with ByteReadCache(source['input']) as raw_file, uproot.open(raw_file,array_cache=None,decompression_executor=uproot.source.futures.TrivialExecutor(),interpretation_executor=uproot.source.futures.TrivialExecutor()) as file:
        tree=file['nt'];present=set(tree.keys())
        needed=['run','eventID']+['Track_'+n for n in TRACK]+['Track_hitSet']+['truth_'+n for n in TRUTH]+MATCH+[s+'_'+k for s in SCINT for k in ['raw_charge','status']]
        required=['run','eventID','Track_pz0','Track_px0','Track_py0','Track_charge']+['truth_'+n for n in TRUTH]+MATCH[:4]+[s+'_'+k for s in SCINT for k in ['raw_charge','status']]
        assert set(required)<=present,sorted(set(required)-present)
        branches=[n for n in needed if n in present]
        schemas=[dict(source=sid,branch=n,present=n in present,typename=tree[n].typename if n in present else 'missing') for n in needed]
        # Only IDs are read over the file; all track/truth payload is sparse, requested identities only.
        ids=tree['eventID'].array(library='np');assert len(ids)==len(np.unique(ids));lookup={int(e):i for i,e in enumerate(ids)}
        selected=[]
        for r in records:
            entry=lookup[r['eventID']]
            if r['input_entry']>=0:assert entry==r['input_entry']
            selected.append((entry,r))
        selected.sort(key=lambda pair:pair[0])
        for entry,r in selected:
            arr=tree.arrays(branches,entry_start=entry,entry_stop=entry+1,library='ak')
            event,tt,ee,ll=analyze(arr,r,present);event['input_entry']=entry;result.append(event);tracks.extend(tt);edges.extend(ee);labels.extend(ll)
        perf=dict(source=sid,available=True,requested_bytes=int(file.file.source.num_requested_bytes),requested_requests=int(file.file.source.num_requests),payload_records=len(records),identity_branch_entries=len(ids),raw_entries=tree.num_entries,branch_count=len(branches),source_read_bytes=raw_file.read_bytes,source_read_requests=raw_file.read_requests,byte_cache_hits=raw_file.hits,reason='complete',**cost(start))
    print('source',sid,'payload',len(records),'wall_s',round(perf['wall_s'],3),flush=True)
    return perf,result,tracks,edges,labels,schemas


def execute(qa=False,processes=8):
    start=time.perf_counter(),time.process_time();plan=json.loads((CACHE/'cohort.json').read_text());records=[r for r in plan['records'] if r['qa']] if qa else plan['records']
    if qa:assert len(records)==40
    tasks=[(s,[r for r in records if r['source']==s['source']]) for s in plan['sources']];tasks=[t for t in tasks if t[1]]
    if qa:results=[read_source(t) for t in tasks]
    else:
        assert json.loads((OUT/'admission.json').read_text())['passed']
        with mp.get_context('fork').Pool(processes) as pool:results=pool.map(read_source,tasks,chunksize=1)
    # TSV permits NaN as explicit missing; no silent finite fallback or event deletion.
    def write(name,rr):
        if rr:
            filename=('QA_' if qa else '')+name+'.tsv'
            if name in ['events','candidates','relations','truth_diagnostics']:
                with (CACHE/filename).open('w') as stream:
                    writer=csv.DictWriter(stream,fieldnames=list(rr[0]),delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rr)
            else:table(filename,rr)
    combined=[sum((r[j] for r in results),[]) for j in range(1,6)];performance=[r[0] for r in results]
    # Missing rows have fewer fields: normalize event schema for the table.
    events=combined[0];keys=list(next(r for r in events if r['available']))
    for r in events:
        for k in keys:r.setdefault(k,float('nan'))
    write('events',events);write('candidates',combined[1]);write('relations',combined[2]);write('truth_diagnostics',combined[3]);write('schema',combined[4]);write('performance',performance)
    child=resource.getrusage(resource.RUSAGE_CHILDREN)
    summary=dict(passed=True,QA=qa,requested_records=len(records),unique_incoming=len({r['key_id'] for r in records}),available_records=sum(bool(r['available']) for r in events),sources=len(tasks),processes=1 if qa else processes,requested_bytes=sum(p['requested_bytes'] for p in performance),requested_requests=sum(p['requested_requests'] for p in performance),source_read_bytes=sum(p['source_read_bytes'] for p in performance),source_read_requests=sum(p['source_read_requests'] for p in performance),byte_cache_hits=sum(p['byte_cache_hits'] for p in performance),source_CPU_s=sum(p['CPU_s'] for p in performance),child_CPU_s=child.ru_utime+child.ru_stime,tracks=len(combined[1]),relations=len(combined[2]),shared_hit_identity_available=False,new_fits=0,test_payload_records=0,**cost(start))
    save('QA.json' if qa else 'extraction.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','qa','worker']);parser.add_argument('--processes',type=int,default=8);args=parser.parse_args()
    if args.action=='prepare':prepare()
    else:execute(args.action=='qa',args.processes)
