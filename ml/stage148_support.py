"""First original train parent with positive mu and other-root Ecal response."""
import csv
import gzip
import json
import resource
import time
from pathlib import Path

OUT = Path('workbook/stage148_energy_ml')


def ecal(record):
    arrays = [row['all_MeV'] for name, row in record['lineage']['deposits'].items() if 'ecal' in name.lower()]
    assert all(len(row) == 3 for row in arrays)
    return [sum(row[j] for row in arrays) for j in range(3)]


def main():
    tick, cpu = time.perf_counter(), time.process_time()
    with gzip.open('ntuples/energy_ml_stage131/production_cases.json.gz', 'rt') as stream:
        cases = json.load(stream)
    with gzip.open('ntuples/energy_ml_stage137/boundary_evidence.json.gz', 'rt') as stream:
        evidence = json.load(stream)
    assert len(cases) == len(evidence) == 4032
    for case in cases[:64]:
        assert str(case['frame_index']) in evidence
        ecal(evidence[str(case['frame_index'])]['report'])
    counts, eligible = {}, []
    for case in cases:
        if case['role'] != 1:
            continue
        record = evidence[str(case['frame_index'])]['report']
        energies = ecal(record)
        mixed = energies[0] > 0 and energies[1] > 0
        key = (case['stratum'], case['component'], record['original_selected_N'])
        row = counts.setdefault(key, dict(stratum=key[0], component=key[1], original_selected=key[2],
                                          parents=0, positive_Ecal=0, mixed_Ecal=0))
        row['parents'] += 1
        row['positive_Ecal'] += int(sum(energies) > 0)
        row['mixed_Ecal'] += int(mixed)
        if mixed:
            eligible.append(dict(frame_index=case['frame_index'], case=case,
                                 Ecal_all_MeV=energies, original_selected=key[2]))
    eligible.sort(key=lambda row: row['frame_index'])
    chosen = eligible[:1]
    with (OUT/'support.tsv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(next(iter(counts.values()))), delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows(counts.values())
    result = dict(input_parents=len(cases), train_parents=sum(row['parents'] for row in counts.values()),
                  eligible_mixed_Ecal=len(eligible), selected_indices=[row['frame_index'] for row in chosen],
                  selected_controls=chosen, preflight_entries=64, preflight_passed=True,
                  CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
                  RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  scope='Original role1 only, no risk/clip/energy cut; first mixed all-time parent, not same-channel-window certification',
                  new_G4=0, new_energy_fits=0, reserved_forward=0)
    (OUT/'support.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result, flush=True)


if __name__ == '__main__':
    main()
