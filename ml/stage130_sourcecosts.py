"""Stdlib source-level producer costs and I/O counters, never double-count CPU."""
import csv
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage130'


def main():
    contract = json.loads((OUT / 'production_contract.json').read_text())
    plan = json.loads((OUT / 'source_protocol.json').read_text())
    records = []
    io = dict(PHYS_requested_uproot_B=0, selected_ntuple_requested_uproot_B=0, production_parentmap_ROOT_B=0)
    compact = OUT / 'source_evidence.json.gz'
    if compact.exists():
        with gzip.open(compact, 'rt') as stream:
            saved = {r['index']: r for r in json.load(stream)}
    else:
        saved = None
    for index in contract['all_source_indices']:
        phase = 'support' if index in contract['pilot_reused'] else 'production'
        directory = CACHE / f'{phase}_{index}'
        if saved is None:
            metadata = {name: json.loads((directory / name).read_text())
                        for name in ['source_qa.json', 'request_summary.json'] + (['parentmap.json'] if phase == 'production' else [])}
            times = {p.name: p.read_text() for p in sorted(directory.glob('*_time.txt'))}
        else:
            metadata, times = saved[index]['metadata'], saved[index]['times']
        qa, request = metadata['source_qa.json'], metadata['request_summary.json']
        meta = qa['feature_metadata']
        for name, text in sorted(times.items()):
            number = lambda key: float(re.search(re.escape(key)+r':\s*([0-9.]+)', text)[1])
            elapsed = re.search(r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\):\s*([0-9:.]+)', text)[1]
            records.append(dict(index=index, component=plan['sources'][index]['component'],
                step=Path(name).stem, selected_N=qa['selected_N'],
                CPU_s=number('User time (seconds)')+number('System time (seconds)'),
                wall_s=sum(float(v)*60**j for j, v in enumerate(reversed(elapsed.split(':')))),
                RSS_KiB=number('Maximum resident set size (kbytes)')))
        # Read counters describe logical requests, not total physical network.
        io['PHYS_requested_uproot_B'] += request['requested_bytes']
        io['selected_ntuple_requested_uproot_B'] += meta['requested_uproot_bytes']
        if phase == 'production':
            io['production_parentmap_ROOT_B'] += metadata['parentmap.json']['ROOT_read_bytes']
    with (OUT / 'source_step_costs.tsv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]), delimiter='\t',
                                lineterminator='\n', quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader()
        writer.writerows(records)
    summary = dict(nested_steps_CPU_s=sum(r['CPU_s'] for r in records),
        max_individual_GNU_RSS_KiB=max(r['RSS_KiB'] for r in records), logical_read_counters=io,
        components={c: dict(sources=sum(plan['sources'][i]['component'] == c for i in contract['all_source_indices']),
            nested_steps_CPU_s=sum(r['CPU_s'] for r in records if r['component'] == c)) for c in ['pi', 'k', 'charm']},
        scope='successful source steps only;pilotEVNT linkage separately measured;GNU childCPU is nested in scheduler total and never added;RSS is max individual process tree observation,not simultaneous job aggregate;full RDO/networkphysical I/O unmeasured')
    (OUT / 'source_cost_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(summary)


if __name__ == '__main__':
    main()
