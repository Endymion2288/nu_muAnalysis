"""Frozen full-point geometry: batch-only extraction; no truth ROOT branches."""
import argparse
import json
import math
import multiprocessing as mp
import resource
import time
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

import stage105_point_feasibility as geometry
from stage105_point_feasibility import canonical, planes, local_edges, target_counts

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage106_energy_ml'
CACHE = ROOT/'ntuples/energy_ml_stage106'
SEED = 2026110506


def save(name, obj):
    (OUT/name).write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def arrays(path):
    with np.load(path) as z:
        return {k: z[k] for k in z.files}


def cost(start):
    return dict(CPU_s=time.process_time()-start[1], wall_s=time.perf_counter()-start[0],
                peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)


def table(name, rows):
    import csv
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w') as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter='\t', lineterminator='\n')
        w.writeheader()
        w.writerows({k: r.get(k, 'NA') if r.get(k) is not None else 'NA' for k in fields} for r in rows)


def read_source(task):
    source, records = task
    tick = time.perf_counter(), time.process_time()
    pp = dict(source=source['source'], N=len(records), available_N=0, payload_CPU_s=0.,
              edge_build_CPU_s=0., interface_requested_bytes=0, source_read_bytes=0,
              invalid_points=0, max_pz_difference_GeV=0., float32_loss_mm=0.)
    points, available, entries, invalid_counts = [], [], [], []
    schema = []
    path = source['input']
    if not path:
        for r in records:
            points.append(np.empty((0,3),np.float32));available.append(False);entries.append(-1);invalid_counts.append(0)
    else:
        assert Path(path).is_file(), ('New missing source', source['source'])
        raw = geometry.ByteCache(path)
        try:
            with uproot.open(raw, array_cache=None,
                decompression_executor=uproot.source.futures.TrivialExecutor(),
                interpretation_executor=uproot.source.futures.TrivialExecutor()) as f:
                tree = f['nt']
                names = ['run','eventID','SpacePoints','SpacePoint_x','SpacePoint_y','SpacePoint_z','Track_pz0']
                assert all(k in tree for k in names), ('Required schema missing', source['source'])
                schema = [dict(source=source['source'],branch=k,typename=tree[k].typename) for k in names]
                lookup = None
                if any(r['input_entry'] < 0 for r in records):
                    ids = tree['eventID'].array(library='np')
                    assert len(np.unique(ids)) == len(ids)
                    lookup = {int(e):i for i,e in enumerate(ids)}
                ordered = sorted(records, key=lambda r:r['input_entry'] if r['input_entry']>=0 else lookup[r['eventID']])
                for r in ordered:
                    t = time.process_time()
                    entry = r['input_entry'] if r['input_entry']>=0 else lookup[r['eventID']]
                    a = tree.arrays(names,entry_start=entry,entry_stop=entry+1,library='ak')
                    assert int(a['run'][0])==r['run'] and int(a['eventID'][0])==r['eventID']
                    delta = abs(float(np.nanmax(ak.to_numpy(a['Track_pz0'][0])))/1000-r['pz_GeV'])
                    assert delta < 2e-4
                    pp['max_pz_difference_GeV'] = max(pp['max_pz_difference_GeV'],delta)
                    xyz = np.column_stack([ak.to_numpy(a['SpacePoint_'+k][0]) for k in 'xyz'])
                    assert len(xyz)==int(a['SpacePoints'][0])
                    plane,_ = planes(xyz)
                    invalid = int((plane<0).sum())
                    xyz, plane = canonical(xyz,plane)
                    if np.isfinite(xyz).all():
                        loss = float(abs(xyz.astype('float32').astype(float)-xyz).max(initial=0))
                        pp['float32_loss_mm'] = max(pp['float32_loss_mm'],loss)
                        assert loss<=.002
                    valid = invalid==0
                    if valid:
                        edge_tick = time.process_time()
                        edges = local_edges(xyz,plane)
                        assert len(edges)<=16*len(xyz)
                        pp['edge_build_CPU_s'] += time.process_time()-edge_tick
                    pp['invalid_points'] += invalid
                    pp['payload_CPU_s'] += time.process_time()-t
                    points.append((r['row'],xyz.astype('float32')))
                    available.append(valid);entries.append(entry);invalid_counts.append(invalid)
                pp['uproot_requested_bytes'] = int(f.file.source.num_requested_bytes)
        finally:
            raw.stream.close()
            pp.update(interface_requested_bytes=raw.request_bytes, source_read_bytes=raw.read_bytes)
        # Restore records ordering after sparse native entry order.
        byrow = {int(v[0]):(v[1],a,e,ic) for v,a,e,ic in zip(points,available,entries,invalid_counts)}
        points,available,entries,invalid_counts = zip(*(byrow[r['row']] for r in records))
    counts = np.array([len(v) for v in points],np.int32)
    pp.update(available_N=int(sum(available)),**cost(tick))
    print('source',source['source'],'N',len(records),'read',pp['available_N'],flush=True)
    return dict(row=np.array([r['row'] for r in records]),available=np.array(available,bool),
                counts=counts,xyz=np.concatenate(points),input_entry=np.array(entries,np.int32),
                invalid_counts=np.array(invalid_counts,np.int32)),pp,schema


def extract(mode):
    start = time.perf_counter(),time.process_time()
    assert mode in ['qa_extract','train_extract','test_extract']
    geometry.CONFIG = json.loads(json.dumps(geometry.CONFIG))
    geometry.CONFIG['limits']['input_requested_bytes'] = 10_000_000_000
    geometry.REQUESTED = mp.get_context('fork').Value('q',0)
    sources = json.loads((ROOT/'workbook/stage96_energy_ml/sources.json').read_text())
    if mode=='qa_extract':
        plan = json.loads((ROOT/'workbook/stage105_energy_ml/identities.json').read_text())
        records = sorted(plan['records'],key=lambda r:r['row'])
        assert len(records)==len({r['key_id'] for r in records})==40
        assert all(r['role'] in [1,2] for r in records)
    else:
        if mode=='train_extract':
            assert json.loads((OUT/'admission.json').read_text())['passed']
        else:
            assert json.loads((OUT/'before_test.json').read_text())['checkpoints_and_offsets_frozen']
        # Identity columns only, no test feature/target payload.
        with np.load(ROOT/'ntuples/energy_ml_stage87/split.npz') as z:
            m = {k:z[k] for k in ['role','key_id','run','eventID','origin','source']}
        with np.load(ROOT/'ntuples/energy_ml_stage94/evaluation_input.npz') as z:
            oldrow,oldpz=z['row'],z['pz']
        selected = np.flatnonzero(m['role']==3 if mode=='test_extract' else np.isin(m['role'],[1,2]))
        ix=np.searchsorted(oldrow,selected);np.testing.assert_array_equal(oldrow[ix],selected)
        records = [dict(row=int(r),key_id=int(m['key_id'][r]),source=f"{m['origin'][r]}:{m['source'][r]}",
                    role=int(m['role'][r]),run=int(m['run'][r]),eventID=int(m['eventID'][r]),
                    input_entry=-1,pz_GeV=float(oldpz[j])) for r,j in zip(selected,ix)]
    tasks = [(s,[r for r in records if r['source']==s['source']]) for s in sources]
    tasks = [t for t in tasks if t[1]]
    with mp.get_context('fork').Pool(8) as pool:
        results = list(pool.imap_unordered(read_source,tasks,chunksize=1))
    allrows = np.concatenate([r[0]['row'] for r in results]);order=np.argsort(allrows)
    cnt = np.concatenate([r[0]['counts'] for r in results]);off=np.r_[0,np.cumsum(cnt)]
    xyz = np.concatenate([r[0]['xyz'] for r in results])
    packed = dict(row=allrows[order],xyz=np.concatenate([xyz[off[i]:off[i+1]] for i in order]),
                  offsets=np.r_[0,np.cumsum(cnt[order])])
    for k in ['available','input_entry','invalid_counts']:
        packed[k] = np.concatenate([r[0][k] for r in results])[order]
    expected = np.array(sorted(r['row'] for r in records))
    np.testing.assert_array_equal(packed['row'],expected)
    rolemap = {r['row']:r['role'] for r in records}
    packed['role'] = np.array([rolemap[int(r)] for r in expected],np.int8)
    name={'qa_extract':'QA','train_extract':'train_cal','test_extract':'test'}[mode]
    path=CACHE/(name+'_coordinates.npz')
    np.savez_compressed(path,**packed)
    cachebytes=sum(p.stat().st_size for p in CACHE.glob('*coordinates.npz'))
    assert cachebytes<=512000000
    perf=[r[1] for r in results]
    table(name+'_source_cost.tsv',perf);table(name+'_schema.tsv',sum((r[2] for r in results),[]))
    summary=dict(passed=True,mode=mode,records=len(records),sources=len(tasks),
        available=int(packed['available'].sum()),missing=int((~packed['available']).sum()),
        total_original_points=int(cnt.sum()),max_original_points=int(cnt.max()),
        invalid_original_points=int(packed['invalid_counts'].sum()),
        max_native_pz_difference_GeV=max(r['max_pz_difference_GeV'] for r in perf),
        float32_loss_mm=max(r['float32_loss_mm'] for r in perf),
        source_CPU_s=sum(r['CPU_s'] for r in perf),payload_CPU_s=sum(r['payload_CPU_s'] for r in perf),
        edge_build_CPU_s=sum(r['edge_build_CPU_s'] for r in perf),
        interface_requested_bytes=geometry.REQUESTED.value,
        source_read_bytes=sum(r['source_read_bytes'] for r in perf),
        cached_coordinate_bytes=path.stat().st_size,total_coordinate_cache_bytes=cachebytes,
        role_records={str(c):int((packed['role']==c).sum()) for c in [1,2,3]},
        test_payload_records=int((packed['role']==3).sum()),optimizer_steps=0,**cost(start))
    if mode=='qa_extract':
        assert summary['available']==37 and summary['missing']==3
        per_event=summary['payload_CPU_s']/37
        fixed=sum(max(0,r['CPU_s']-r['payload_CPU_s']) for r in perf if r['available_N'])/22
        summary['projected_full_extraction_CPU_s']=3*(per_event*70332+fixed*280)+1000
    else:
        expectedMissing=688 if mode=='train_extract' else 356
        invalid_events=int((packed['invalid_counts']>0).sum())
        assert summary['missing']==expectedMissing+invalid_events, 'New missing source: stop contract before fit'
        summary['invalid_geometry_events']=invalid_events
    save(name+'_extraction.json',summary)
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['qa_extract','train_extract','test_extract']);a=p.parse_args();extract(a.mode)
