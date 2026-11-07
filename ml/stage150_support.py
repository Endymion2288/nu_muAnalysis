"""Frozen role1 Ecal-overflow support, no transport or artificial censoring."""
import csv
import gzip
import json
import resource
import time
from collections import Counter
from pathlib import Path

import numpy as np

OUT = Path('workbook/stage150_energy_ml')


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    with gzip.open('ntuples/energy_ml_stage131/production_cases.json.gz', 'rt') as stream:
        cases = json.load(stream)
    with gzip.open('ntuples/energy_ml_stage137/boundary_evidence.json.gz', 'rt') as stream:
        evidence = json.load(stream)
    with np.load('ntuples/energy_ml_stage131/matched_input.npz') as source:
        frames, status = source['frame_index'].copy(), source['calo_status'].copy()
    assert len(cases) == len(evidence) == 4032
    assert status.shape == (len(frames), 4) and len(np.unique(frames)) == len(frames)
    by_frame = {int(frame): row for frame, row in zip(frames, status)}
    for case in cases[:64]:
        assert str(case['frame_index']) in evidence
        assert 'original_selected_N' in evidence[str(case['frame_index'])]['report']
    counts, eligible, status_counts = {}, [], Counter()
    for case in cases:
        index = int(case['frame_index'])
        if case['role'] != 1:
            continue
        original_selected = int(evidence[str(index)]['report']['original_selected_N'])
        row = by_frame.get(index)
        valid = bool(row is not None and np.isfinite(row).all() and (row >= 0).all() and (row == np.floor(row)).all())
        clipped = bool(valid and np.any(row.astype(np.int64) & 4))
        key = (case['stratum'], case['component'], original_selected)
        count = counts.setdefault(key, dict(stratum=key[0], component=key[1], original_selected=key[2],
            parents=0, status_reference=0, status_unknown=0, overflow_parents=0))
        count['parents'] += 1
        count['status_reference'] += int(valid)
        count['status_unknown'] += int(not valid)
        count['overflow_parents'] += int(clipped)
        if valid:
            status_counts.update(str(int(value)) for value in row)
        if clipped:
            eligible.append(dict(frame_index=index, case=case, original_calo_status=row.tolist(), original_selected=original_selected))
    eligible.sort(key=lambda row: row['frame_index'])
    with (OUT/'support.tsv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(next(iter(counts.values()))), delimiter='\t', lineterminator='\n')
        writer.writeheader(); writer.writerows(counts.values())
    result = dict(passed=True, input_parents=len(cases), matched_selected_status_rows=len(frames),
        train_parents=sum(r['parents'] for r in counts.values()),
        train_status_reference_N=sum(r['status_reference'] for r in counts.values()),
        train_status_unknown_N=sum(r['status_unknown'] for r in counts.values()),
        train_Calo_status_counts=dict(status_counts), eligible_overflow_parents=len(eligible),
        selected_indices=[r['frame_index'] for r in eligible[:1]], selected_controls=eligible[:1],
        preflight_entries=64, preflight_passed=True,
        CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
        RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        actual_ADC_clipping_measured=False, new_G4=0, fits=0, reserved_forward=0,
        scope='Existing role1 retained selected status support only; no missing status imputation, population clipping claim or expanded inventory')
    (OUT/'support.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result, flush=True)


if __name__ == '__main__':
    main()
