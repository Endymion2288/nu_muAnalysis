"""Bounded run15838 inventory and identity headers; no exposure certification."""
import gzip
import json
import os
import re
import resource
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import uproot

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage167_energy_ml'
BRANCHES = ['run', 'eventID', 'eventTime']
PHYS = re.compile(r'Faser-Physics-015838-(\d{5})-(\d{5})-r0022-PHYS\.root\Z')
RAW = re.compile(r'Faser-Physics-015838-(\d{5})\.raw\Z')


def plan():
    return json.loads((OUT / 'protocol.json').read_text())


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def inventory():
    result = {}
    for kind, regex, cap in [('PHYS', PHYS, 64), ('RAW', RAW, 4096)]:
        directory = plan()['inputs'][kind + '_directory']
        # Exactly one nonrecursive listing here; no RAW stat or payload reads.
        names = sorted(os.listdir(directory))
        matched, other = [], []
        for name in names:
            match = regex.fullmatch(name)
            if match:
                record = dict(name=name, path=directory + '/' + name)
                if kind == 'PHYS':
                    record.update(first_index=int(match[1]), last_index=int(match[2]))
                    assert record['first_index'] <= record['last_index']
                else:
                    record['index'] = int(match[1])
                matched.append(record)
            else:
                other.append(name)
        assert 0 < len(matched) <= cap, (kind, len(matched), cap)
        result[kind] = dict(directory=directory, matched=matched, nonmatching=other,
                            listing_N=len(names), cap=cap)
    return result


def coverage(inv):
    claims = {}
    for r in inv['PHYS']['matched']:
        for i in range(r['first_index'], r['last_index'] + 1):
            claims.setdefault(i, []).append(r['name'])
    raw = {r['index'] for r in inv['RAW']['matched']}
    declared = set(claims)
    return dict(PHYS_files=len(inv['PHYS']['matched']), RAW_files=len(raw),
        claimed_indices=len(declared), claimed_first=min(declared), claimed_last=max(declared),
        overlapping_claims={str(k): v for k, v in claims.items() if len(v) > 1},
        internal_claim_gaps=sorted(set(range(min(declared), max(declared) + 1)) - declared),
        RAW_without_PHYS_claim=sorted(raw - declared), claimed_without_actual_RAW=sorted(declared - raw),
        processing_proven=False, dataset_luminosity_pb_inv=None,
        interpretation='Filename ranges are declarations; actual consumed inputs, DAQ livetime and exposure remain unproven.')


def metadata(source, classes):
    records = {}
    for name, cls in classes.items():
        if name == 'nt':
            continue
        if name in ['meta', 'MetaData'] and cls == 'TTree':
            tree = source[name]
            types = tree.typenames()
            record = dict(classname=cls, N=int(tree.num_entries), schema=types,
                          scalar_rows={}, omitted_nonscalar=[])
            for b in tree.keys():
                interpretation = tree[b].interpretation
                dtype = getattr(interpretation, 'numpy_dtype', None)
                if dtype is not None and dtype.kind in 'biuf' and dtype.shape == ():
                    a = tree[b].array(entry_stop=4, library='np')
                    # Nonfinite producer values are explicit strings, never invented measurements.
                    record['scalar_rows'][b] = [v.item() if np.isfinite(v) else str(v) for v in a]
                else:
                    record['omitted_nonscalar'].append(b)
            assert len(json.dumps(record, allow_nan=False).encode()) <= 65536
            records[name] = record
        elif cls in ['TNamed', 'TObjString'] and re.search(r'meta|config|input|provenance', name, re.I):
            key = source.key(name)
            if key.fObjlen > 65536:
                records[name] = dict(classname=cls, text=None, reason='object exceeds64KiB')
            else:
                obj = source[name]
                text = str(obj) if cls == 'TObjString' else str(obj.member('fTitle'))
                records[name] = dict(classname=cls, text=text if len(text.encode()) <= 65536 else None)
    assert len(json.dumps(records, allow_nan=False).encode()) <= 65536
    return records


def read_file(record):
    cpu, wall = time.process_time(), time.perf_counter()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with uproot.open(record['path'], array_cache=None, decompression_executor=pool,
                         interpretation_executor=pool) as source:
            classes = source.classnames(recursive=False, cycle=False)
            assert classes.get('nt') == 'TTree', classes
            tree = source['nt']; n = int(tree.num_entries); assert n > 0
            types = {b: tree[b].typename for b in BRANCHES}
            rows = []
            for i in [0, n - 1]:
                a = tree.arrays(BRANCHES, entry_start=i, entry_stop=i + 1, library='np')
                assert all(np.issubdtype(a[b].dtype, np.integer) for b in BRANCHES)
                rows.append({b: int(a[b][0]) for b in BRANCHES})
            assert all(r['run'] == 15838 for r in rows)
            ref = record['path'] == plan()['inputs']['reference_PHYS']
            if ref:
                with gzip.open(ROOT / plan()['inputs']['reference_prefix'], 'rt') as f:
                    old = json.load(f)[:64]
                a = tree.arrays(BRANCHES, entry_stop=64, library='np')
                assert all(int(a[b][i]) == old[i][b] for i in range(64) for b in BRANCHES)
                expected = json.loads((ROOT / plan()['inputs']['reference_summary']).read_text())
                assert n == expected['source_N'] == 780874
                assert rows[0]['eventTime'] == expected['time_min_s']
                assert rows[-1]['eventTime'] == expected['time_max_s']
            physical = dict(**record, N=n, branch_types=types, first=rows[0], last=rows[1],
                            top_level_keys=classes, metadata=metadata(source, classes), reference64_exact=ref)
            timing = dict(path=record['path'], CPU_s=time.process_time() - cpu,
                          wall_s=time.perf_counter() - wall,
                          read_bytes=int(source.file.source.num_requested_bytes),
                          RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return physical, timing
