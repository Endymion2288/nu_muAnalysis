"""EVNT persistent headers and bounded numeric producer metadata only."""
import json
import re
import resource
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import uproot

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage168_energy_ml'
NUMERIC = re.compile(r'(?:u?int(?:8|16|32|64)_t|(?:unsigned )?(?:char|short|int|long|long long)|float|double|bool|U?Int_t|U?Long64_t|Float_t|Double_t|Bool_t|U?Short_t|U?Char_t)\Z')
TOKENS = re.compile(r'meta|config|input|provenance|norm|param', re.I)


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def inputs():
    return json.loads((OUT / 'inputs.json').read_text())


def read_file(path):
    cpu, wall = time.process_time(), time.perf_counter()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with uproot.open(path, array_cache=None, decompression_executor=pool,
                         interpretation_executor=pool) as f:
            keys = f.classnames(recursive=False, cycle=False)
            assert keys.get('CollectionTree') == 'TTree', keys
            t = f['CollectionTree']; n = int(t.num_entries); assert n > 0
            schema = t.typenames()
            metadata = {}
            for name, cls in keys.items():
                if name == 'CollectionTree':
                    continue
                if cls == 'TTree':
                    tree = f[name]; types = tree.typenames()
                    assert len(json.dumps(types).encode()) <= 65536, name
                    record = dict(classname=cls, N=int(tree.num_entries), schema=types,
                                  scalar_rows={}, omitted_branches=[])
                    # POOL event data headers are not silently treated as producer metadata.
                    for b in tree.keys():
                        if TOKENS.search(name) and NUMERIC.fullmatch(tree[b].typename):
                            a = tree[b].array(entry_stop=4, library='np')
                            assert a.ndim == 1 and a.dtype.kind in 'biuf'
                            record['scalar_rows'][b] = [v.item() if np.isfinite(v) else str(v) for v in a]
                        else:
                            record['omitted_branches'].append(b)
                    assert len(json.dumps(record, allow_nan=False).encode()) <= 65536, name
                    metadata[name] = record
                elif cls in ['TNamed', 'TObjString'] and TOKENS.search(name):
                    if f.key(name).fObjlen > 65536:
                        metadata[name] = dict(classname=cls, text=None, reason='object exceeds64KiB')
                    else:
                        obj = f[name]
                        value = str(obj) if cls == 'TObjString' else str(obj.member('fTitle'))
                        metadata[name] = dict(classname=cls, text=value if len(value.encode()) <= 65536 else None)
            assert len(json.dumps(metadata, allow_nan=False).encode()) <= 131072
            record = dict(path=path, N=n, CollectionTree_schema=schema, top_level_keys=keys,
                          metadata=metadata, CollectionTree_payload_read=False,
                          generator_weight_normalization_certified=False)
            timing = dict(path=path, CPU_s=time.process_time() - cpu, wall_s=time.perf_counter() - wall,
                          read_bytes=int(f.file.source.num_requested_bytes),
                          RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return record, timing


def logged_ranges(records):
    source = json.loads((ROOT / 'workbook/stage130_energy_ml/source_protocol.json').read_text())
    byindex = {r['index']: r for r in source['sources']}
    counts = {r['path']: r['N'] for r in records}
    proof = json.loads((ROOT / 'workbook/stage130_energy_ml/parent_range_proof.json').read_text())
    result = []
    for r in proof['sources']:
        s = byindex[r['index']]
        assert s['EVNT'] in counts
        commands = []
        for log in r['boundary_logs']:
            # Parse the retained literal command; do not reread logs or infer internal successes.
            import shlex
            tokens = shlex.split(log['command'])
            assert tokens[0] == 'faser_simulate.py' and tokens[1] == s['EVNT']
            commands.append(dict(skip=int(tokens[tokens.index('--skip')+1]), count=int(tokens[tokens.index('-n')+1])))
        assert len(commands) == 2 and commands[0]['skip'] == r['skip']
        assert commands[-1]['skip'] + commands[-1]['count'] == r['skip'] + r['count']
        valid = 0 <= r['skip'] < r['skip'] + r['count'] <= counts[s['EVNT']]
        result.append(dict(index=r['index'], run=s['run'], path=s['EVNT'], skip=r['skip'], count=r['count'],
            generated_N=counts[s['EVNT']], logged_boundaries=commands, within_actual_N=valid,
            entire_range_success_proven=False))
    return result
