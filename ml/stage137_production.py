"""Only the newly required boundary observer replay; no digi/reco or selection."""
import concurrent.futures
import gzip
import json
import sys
from pathlib import Path
import stage135_pilot as pilot

ROOT = Path.cwd()
OUT = ROOT/'workbook/stage137_energy_ml'
pilot.OUT = OUT
pilot.CACHE = ROOT/'ntuples/energy_ml_stage137'

def main():
    index = int(sys.argv[1])
    protocol = json.loads((OUT/'protocol.json').read_text())
    with gzip.open(ROOT/'ntuples/energy_ml_stage131/production_cases.json.gz', 'rt') as f:
        cases = {r['frame_index']:r for r in json.load(f)}
    with gzip.open(ROOT/'ntuples/energy_ml_stage131/parent_evidence.json.gz', 'rt') as f:
        evidence = {r['index']:r['reports'] for r in json.load(f)}
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        tasks = {pool.submit(pilot.worker, cases[i], evidence[i]):i
                 for i in protocol['batches'][index]}
        for future in concurrent.futures.as_completed(tasks):
            try:
                results.append(future.result())
            except Exception as error:
                results.append(dict(index=tasks[future], successful=False, error=repr(error)))
    (OUT/f'production_results_{index}.json').write_text(json.dumps(results, indent=2)+'\n')
    assert all(r['successful'] for r in results), results

if __name__ == '__main__':
    main()
