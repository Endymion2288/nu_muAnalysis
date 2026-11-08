"""Acquire named official GRL inputs and time the original first1024 rows."""
import csv
import json
import math
import resource
import time

import numpy as np
import uproot
import yaml
from stage158_finalize import archive_exact
from stage166_common import ROOT, OUT, CACHE, REQUIRED, OPTIONAL, plan, write, table, snapshot, save_prefix, flags


def main():
    cpu, tick = time.process_time(), time.perf_counter(); p = plan()
    config = yaml.safe_load((ROOT / p['inputs']['GRL_config']).read_text())
    paths = config['grl_jsons'] + config['grl_csvs']; assert len(paths) == 6
    payload = {}; files = []; matched_json = []; matched_csv = []
    for name in paths:
        from pathlib import Path
        path = Path(name); data = path.read_bytes(); payload[str(path).lstrip('/')] = data
        files.append(dict(path=str(path), bytes=len(data)))
        if path.suffix == '.json':
            content = json.loads(data)
            if '15838' in content:
                matched_json.append(dict(path=str(path), record=content['15838']))
        else:
            rows = list(csv.reader(data.decode().splitlines())); header = rows[0]
            assert len(header) >= 4 and header[3].strip().lower().replace('_', '') == 'lumirec', header
            for row in rows[1:]:
                if not row or row[0].startswith('#'):
                    continue
                if int(row[0]) == 15838:
                    lumi = float(row[3]); assert math.isfinite(lumi) and lumi >= 0
                    matched_csv.append(dict(path=str(path), header=header, row=row, recorded_lumi_pb_inv=lumi))
    assert len(matched_json) == len(matched_csv) == 1
    record = matched_json[0]['record']
    ranges = lambda key: [[int(r['start_utime']), int(r['stop_utime'])] for r in record.get(key, [])]
    g = dict(run=15838, JSON=matched_json[0], CSV=matched_csv[0], files=files,
        stable_ranges_s=ranges('stable_list'), excluded_ranges_s=ranges('excluded_list'),
        luminosity_unit_basis='Repository grl_config.yaml: lumi_rec in pb^-1; not an independent luminosity calibration',
        dataset_luminosity_pb_inv=None)
    assert g['stable_ranges_s'] and all(lo <= hi for lo, hi in g['stable_ranges_s'] + g['excluded_ranges_s'])
    archive_exact(CACHE / 'official_grl_inputs.tar.gz', payload)
    write('grl_input.json', g)
    official_cpu = time.process_time() - cpu
    with uproot.open(p['inputs']['PHYS'], array_cache=None) as source:
        tree = source['nt']; names = set(tree.keys()); assert set(REQUIRED) <= names
        branches = REQUIRED + [b for b in OPTIONAL if b in names]
        assert tree.num_entries == 780874 and tree.num_entries >= 1024
        opened_cpu = time.process_time(); first = tree.arrays(branches, entry_stop=512, library='np')
        middle_cpu, middle_wall = time.process_time(), time.perf_counter()
        second = tree.arrays(branches, entry_start=512, entry_stop=1024, library='np')
        steady_cpu, steady_wall = time.process_time() - middle_cpu, time.perf_counter() - middle_wall
        rows = snapshot(first) + snapshot(second)
        assert len(rows) == 1024 and all(r['run'] == 15838 for r in rows)
        reference = json.loads((ROOT / p['inputs']['reference_manifest']).read_text())['records']
        assert all((r['run'], r['eventID'], r['eventTime']) == (v['run'], v['event'], v['timestamp'])
                   for r, v in zip(rows[:64], reference))
        save_prefix(rows)
        observed = {b: np.concatenate([first[b], second[b]]) for b in branches}
        f = flags(observed, g)
        table('pilot_time_support.tsv', [dict(flag=k, N=int(v.sum())) for k, v in f.items()])
        result = dict(passed=True, N=1024, source_N=int(tree.num_entries), branches=branches,
            missing_optional=sorted(set(OPTIONAL) - names), branch_types={b: tree[b].typename for b in branches},
            original64_identity_exact=True, first512_and_open_CPU_s=middle_cpu - (cpu + official_cpu),
            second512_CPU_s=steady_cpu, second512_wall_s=steady_wall,
            opened_to_first512_CPU_s=middle_cpu - opened_cpu,
            official_inputs_CPU_s=official_cpu, read_bytes=int(source.file.source.num_requested_bytes),
            CPU_s=time.process_time() - cpu, wall_s=time.perf_counter() - tick,
            RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            recorded_run_lumi_pb_inv=matched_csv[0]['recorded_lumi_pb_inv'],
            dataset_lumi_pb_inv=None, energy_fits=0, model_forward=0, new_G4=0, promotion=False)
    write('pilot_summary.json', result); print(result)


if __name__ == '__main__':
    main()
