"""Fixed train/cal PHYS geometry QA. No fit, test payload or point-cloud output."""
import csv
import json
import multiprocessing as mp
import resource
import time
from collections import OrderedDict
from pathlib import Path

import awkward as ak
import numpy as np
import uproot
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage105_energy_ml'
CONFIG = json.loads((OUT/'protocol.json').read_text())
CENTERS = np.array(CONFIG['geometry']['station_centers_mm'])
OFFSETS = np.array(CONFIG['geometry']['layer_offsets_mm'])
REQUESTED = None


def save(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def table(name, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w') as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter='\t', lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


class BudgetExceeded(RuntimeError):
    pass


class ByteCache:
    """Same exact-range reuse as Stage95, with a shared pre-read request cap."""
    def __init__(self, path):
        self.stream = open(path, 'rb')
        self.cache = OrderedDict()
        self.size = self.read_bytes = self.calls = self.hits = self.request_bytes = 0

    def seek(self, *args):
        return self.stream.seek(*args)

    def tell(self):
        return self.stream.tell()

    def read(self, n=-1):
        if n < 0:
            raise ValueError('Unbounded ROOT reads are not admitted')
        with REQUESTED.get_lock():
            if REQUESTED.value+n > CONFIG['limits']['input_requested_bytes']:
                raise BudgetExceeded('Shared interface request cap reached before read')
            REQUESTED.value += n
        self.request_bytes += n
        key = (self.tell(), n)
        if key in self.cache:
            data = self.cache.pop(key)
            self.cache[key] = data
            self.stream.seek(key[0]+len(data))
            self.hits += 1
            return data
        data = self.stream.read(n)
        self.read_bytes += len(data)
        self.calls += 1
        if len(data) <= 64*1024**2:
            while self.cache and self.size+len(data) > 64*1024**2:
                _, old = self.cache.popitem(last=False)
                self.size -= len(old)
            self.cache[key] = data
            self.size += len(data)
        return data


def planes(xyz):
    z = xyz[:, 2]
    station = abs(z[:, None]-CENTERS).argmin(1)
    layer = abs(z[:, None]-CENTERS[station, None]-OFFSETS).argmin(1)
    residual = abs(z-CENTERS[station]-OFFSETS[layer])
    valid = np.isfinite(xyz).all(1) & (residual <= 10)
    valid &= ~np.any(abs(xyz) == 999999, axis=1)
    valid &= ~np.all(xyz == -999, axis=1)
    return np.where(valid, station*3+layer, -1), residual


def canonical(xyz, plane):
    order = np.lexsort((xyz[:, 2], xyz[:, 1], xyz[:, 0], plane))
    return xyz[order], plane[order]


def local_edges(xyz, plane):
    edges = []
    for station in range(4):
        for layer in range(2):
            a = np.flatnonzero(plane == station*3+layer)
            b = np.flatnonzero(plane == station*3+layer+1)
            for source, target in [(a, b), (b, a)]:
                if not len(source) or not len(target):
                    continue
                k = min(8, len(target))
                _, neighbor = cKDTree(xyz[target, :2]).query(xyz[source, :2], k=k, workers=1)
                neighbor = np.asarray(neighbor).reshape(len(source), k)
                edges.append(np.column_stack([np.repeat(source, k), target[neighbor.ravel()]]))
    return np.concatenate(edges).astype(np.int64) if edges else np.empty((0, 2), np.int64)


def mask_inputs(xyz, plane, hidden):
    take = plane != hidden
    xyz, plane = canonical(xyz[take], plane[take])
    edges = local_edges(xyz, plane)
    # No original scalar, original length or hidden count enters this tuple.
    counts = np.bincount(plane[plane >= 0], minlength=12)
    return xyz, plane, edges, counts


def target_counts(xyz):
    inside = ((xyz[:, :2] >= -200) & (xyz[:, :2] < 200)).all(1)
    cell = np.full(len(xyz), 256, int)
    bins = np.floor((xyz[inside, :2]+200)/25).astype(int)
    cell[inside] = bins[:, 0]*16+bins[:, 1]
    return np.bincount(cell, minlength=257)


def summarize(xyz, record):
    tick = time.perf_counter()
    plane, residual = planes(xyz)
    finite = np.isfinite(xyz).all(1)
    invalid = plane < 0
    base = dict(point_N=len(xyz), finite_point_N=int(finite.sum()), unmapped_N=int(invalid.sum()),
        all_minus999_N=int(np.all(xyz == -999, axis=1).sum()),
        signed_minus1_coordinate_N=int((xyz == -1).sum()),
        minus999_coordinate_candidates_N=int((xyz == -999).sum()),
        duplicate_xyz_N=len(xyz)-len(np.unique(xyz, axis=0)),
        empty_collection=len(xyz) == 0,
        max_plane_residual_mm=float(residual[finite].max(initial=0)),
        float32_coordinate_loss_mm=float(np.max(abs(xyz.astype('float32').astype(float)-xyz), initial=0)) if finite.all() else None)
    layer_rows = []
    for j in range(12):
        z = plane == j
        layer_rows.append(dict(row=record['row'], plane=j, station=j//3, layer=j%3,
            nominal_z_mm=float(CENTERS[j//3]+OFFSETS[j%3]), point_N=int(z.sum()),
            z_min_mm=float(xyz[z, 2].min()) if z.any() else None,
            z_max_mm=float(xyz[z, 2].max()) if z.any() else None))
    if invalid.any():
        base.update(graph_checked=False, graph_reason='Unmapped/invalid points retained in count; contract needs explicit missing-coordinate bucket')
        return base, layer_rows
    xyz, plane = canonical(xyz, plane)
    edge_tick = time.perf_counter()
    edges = local_edges(xyz, plane)
    edge_wall = time.perf_counter()-edge_tick
    if len(edges):
        assert np.all(plane[edges[:, 0]]//3 == plane[edges[:, 1]]//3)
        assert np.all(abs(plane[edges[:, 0]]-plane[edges[:, 1]]) == 1)
        # Independent brute-force k-nearest distance control on every query in this QA.
        error = 0.
        for source in np.unique(edges[:, 0]):
            for dest_plane in np.unique(plane[edges[edges[:, 0] == source, 1]]):
                actual = edges[(edges[:, 0] == source) & (plane[edges[:, 1]] == dest_plane), 1]
                target = np.flatnonzero(plane == dest_plane)
                expected = np.sort(np.linalg.norm(xyz[target, :2]-xyz[source, :2], axis=1))[:len(actual)]
                measured = np.sort(np.linalg.norm(xyz[actual, :2]-xyz[source, :2], axis=1))
                error = max(error, float(np.max(abs(expected-measured), initial=0)))
        assert error < 1e-10
    else:
        error = 0.
    shuffled = np.random.default_rng(2026110505+record['row']).permutation(len(xyz))
    again, ids = canonical(xyz[shuffled], plane[shuffled])
    np.testing.assert_array_equal(again, xyz)
    np.testing.assert_array_equal(local_edges(again, ids), edges)
    hidden = 3+record['row']%9
    vis = mask_inputs(xyz, plane, hidden)
    # Alter hidden coordinates and append hidden points: visible input must be exact.
    modified = xyz.copy()
    modified[plane == hidden, :2] += [17., -29.]
    modified = np.concatenate([modified, [[1., 2., CENTERS[hidden//3]+OFFSETS[hidden%3]]]*2])
    modified_plane = np.r_[plane, [hidden, hidden]]
    no_leak = mask_inputs(modified, modified_plane, hidden)
    for a, b in zip(vis, no_leak):
        np.testing.assert_array_equal(a, b)
    target = target_counts(xyz[plane == hidden])
    assert int(target.sum()) == int((plane == hidden).sum())
    base.update(graph_checked=True, edge_N=len(edges), edge_bound_16N=16*len(xyz),
        node_coordinate_bytes_float32=12*len(xyz), edge_index_bytes_int32=8*len(edges),
        edge_build_wall_s=edge_wall, brute_force_neighbor_max_mm=error,
        permutation_exact=True, mask_input_exact=True, hidden_plane=hidden,
        hidden_point_N=int((plane == hidden).sum()), visible_point_N=len(vis[0]),
        visible_edge_N=len(vis[2]), target_sum=int(target.sum()), target_overflow_N=int(target[-1]),
        geometry_QA_wall_s=time.perf_counter()-tick)
    assert len(edges) <= 16*len(xyz)
    return base, layer_rows


def source_task(task):
    source, records = task
    start = time.perf_counter(), time.process_time()
    perf = dict(source=source['source'], identities=len(records), requested_bytes=0,
        source_read_bytes=0, source_read_calls=0, cache_hits=0, uproot_requested_bytes=0)
    events, layers, schema = [], [], []
    available = bool(source['input'] and Path(source['input']).is_file())
    if not available:
        events = [dict(row=r['row'], source=r['source'], role=r['role'], component=r['component'],
                       available=False, status='known_source_unavailable') for r in records]
    else:
        raw = ByteCache(source['input'])
        try:
            with uproot.open(raw, array_cache=None,
                decompression_executor=uproot.source.futures.TrivialExecutor(),
                interpretation_executor=uproot.source.futures.TrivialExecutor()) as f:
                tree = f['nt']
                names = ['run', 'eventID', 'SpacePoints', 'SpacePoint_x', 'SpacePoint_y', 'SpacePoint_z', 'Track_pz0']
                schema = [dict(source=source['source'], branch=k, present=k in tree,
                    typename=tree[k].typename if k in tree else 'missing') for k in names]
                missing = [k for k in names if k not in tree]
                for r in sorted(records, key=lambda v: v['input_entry']):
                    row = dict(row=r['row'], source=r['source'], role=r['role'], component=r['component'], available=False)
                    if missing:
                        row['status'] = 'required_schema_missing:'+','.join(missing)
                    else:
                        entry = r['input_entry']
                        assert entry >= 0
                        a = tree.arrays(names, entry_start=entry, entry_stop=entry+1, library='ak')
                        assert int(a['run'][0]) == r['run'] and int(a['eventID'][0]) == r['eventID']
                        pz = ak.to_numpy(a['Track_pz0'][0])/1000
                        assert abs(float(np.nanmax(pz))-r['pz_GeV']) < 2e-4
                        xyz = np.column_stack([ak.to_numpy(a['SpacePoint_'+k][0]) for k in 'xyz'])
                        assert len(xyz) == int(a['SpacePoints'][0]), 'Scalar/vector point counts differ'
                        values, plane_rows = summarize(xyz, r)
                        row.update(available=True, status='ok', input_entry=entry, identity_exact=True,
                                   leading_pz_difference_GeV=abs(float(np.nanmax(pz))-r['pz_GeV']), **values)
                        layers += plane_rows
                    events.append(row)
                perf['uproot_requested_bytes'] = int(f.file.source.num_requested_bytes)
        except BudgetExceeded:
            seen = {r['row'] for r in events}
            events += [dict(row=r['row'], source=r['source'], role=r['role'], component=r['component'],
                            available=False, status='input_budget_not_read') for r in records if r['row'] not in seen]
        finally:
            raw.stream.close()
            perf.update(requested_bytes=raw.request_bytes, source_read_bytes=raw.read_bytes,
                        source_read_calls=raw.calls, cache_hits=raw.hits)
    perf.update(CPU_s=time.process_time()-start[1], wall_s=time.perf_counter()-start[0],
        peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    print('source', source['source'], 'identities', len(records), 'bytes', perf['requested_bytes'], flush=True)
    return events, layers, schema, perf


def worker_cpu_limit():
    # Four children <= 4*170 CPU seconds; parent <= 180: total <= 860.
    resource.setrlimit(resource.RLIMIT_CPU, (170, 170))


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (180, 180))
    global REQUESTED
    tick, cpu = time.perf_counter(), time.process_time()
    plan = json.loads((OUT/'identities.json').read_text())
    records, sources = plan['records'], plan['sources']
    assert len(records) == len({r['key_id'] for r in records}) == 40
    assert all(r['role'] in [1, 2] for r in records)
    REQUESTED = mp.get_context('fork').Value('q', 0)
    tasks = [(s, [r for r in records if r['source'] == s['source']]) for s in sources]
    tasks = [t for t in tasks if t[1]]
    pilot = next(i for i, t in enumerate(tasks) if t[0]['input'])
    first = source_task(tasks.pop(pilot))
    available_first = [r for r in first[0] if r['available']]
    assert available_first, 'Pilot cannot establish payload cost; no expansion'
    ratio = 40/len(first[0])
    projected_cpu = first[3]['CPU_s']*ratio*5+30
    projected_wall = first[3]['wall_s']*ratio*5+30
    projected_bytes = first[3]['requested_bytes']*ratio*3
    admitted = projected_cpu < 900 and projected_wall < 900 and projected_bytes < 1_000_000_000
    save('admission.json', dict(passed=admitted, pilot_identities=len(first[0]),
        pilot_available=len(available_first), CPU_projection_s=projected_cpu,
        serial_wall_projection_s=projected_wall, interface_byte_projection=projected_bytes,
        pilot_performance=first[3], projection_is_heuristic=True))
    results = [first]
    if admitted:
        with mp.get_context('fork').Pool(4, initializer=worker_cpu_limit) as pool:
            results += pool.map(source_task, tasks, chunksize=1)
    else:
        for source, rr in tasks:
            results.append(([dict(row=r['row'], source=r['source'], role=r['role'], component=r['component'],
                 available=False, status='not_admitted') for r in rr], [], [], dict(source=source['source'], identities=len(rr), requested_bytes=0, CPU_s=0, wall_s=0)))
    events = sorted(sum((r[0] for r in results), []), key=lambda v: v['row'])
    layer_rows = sum((r[1] for r in results), [])
    perf = [r[3] for r in results]
    table('events.tsv', events)
    table('planes.tsv', layer_rows)
    table('schema.tsv', sum((r[2] for r in results), []))
    table('source_performance.tsv', perf)
    good = [r for r in events if r['available']]
    graph = [r for r in good if r['graph_checked']]
    summary = dict(passed=admitted and len(graph) == len(good) == 37 and all(r['status'] in ['ok', 'known_source_unavailable'] for r in events),
        requested_identities=40, source_N=len(sources), readable_N=len(good),
        unavailable_N=40-len(good), graph_checked_N=len(graph),
        original_count_alignment=True, original_point_selection_untruncated=True,
        total_points=sum(r['point_N'] for r in good), total_edges=sum(r['edge_N'] for r in graph),
        max_points=max((r['point_N'] for r in good), default=0),
        max_edges=max((r['edge_N'] for r in graph), default=0),
        max_plane_residual_mm=max((r['max_plane_residual_mm'] for r in good), default=0),
        total_unmapped=sum(r['unmapped_N'] for r in good),
        empty_collection_N=sum(r['empty_collection'] for r in good),
        max_coordinate_float32_loss_mm=max((r['float32_coordinate_loss_mm'] or 0 for r in good), default=0),
        edge_distance_independent_max_mm=max((r['brute_force_neighbor_max_mm'] for r in graph), default=0),
        nonempty_hidden_plane_N=sum(r['hidden_point_N'] > 0 for r in graph),
        target_overflow_points=sum(r['target_overflow_N'] for r in graph),
        hidden_coordinate_and_count_input_unchanged=all(r['mask_input_exact'] for r in graph),
        interface_requested_bytes=REQUESTED.value, source_read_bytes=sum(r.get('source_read_bytes', 0) for r in perf),
        uproot_requested_bytes=sum(r.get('uproot_requested_bytes', 0) for r in perf),
        source_CPU_s=sum(r['CPU_s'] for r in perf), new_fits=0, pretraining_steps=0, test_payload_records=0,
        measured_active_readout=False, real_particle_association=False,
        wall_s=time.perf_counter()-tick, CPU_self_s=time.process_time()-cpu,
        CPU_child_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
        peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    assert summary['interface_requested_bytes'] <= 1_000_000_000
    save('complete.json', summary)
    plot(good)
    print(json.dumps(summary, indent=2), flush=True)


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 3.6), layout='constrained')
    good = [r for r in rows if r['graph_checked']]
    ax.scatter([r['point_N'] for r in good], [r['edge_N'] for r in good])
    limit = max((r['point_N'] for r in good), default=1)
    ax.plot([0, limit], [0, 16*limit], '--', label='16N edge bound')
    ax.set(xlabel='All observed SpacePoints / event', ylabel='Directed local edges / event',
           title='Fixed train/cal QA; no point truncation')
    ax.legend()
    fig.savefig(OUT/'graph_cost.svg')
    plt.close(fig)


if __name__ == '__main__':
    main()
