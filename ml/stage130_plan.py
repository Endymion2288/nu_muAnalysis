"""Bounded text inventory of the 22 user-authorized full-depth flux runs."""
import json
import csv
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'workbook/stage130_energy_ml'
BASE = Path('/eos/experiment/fasernu-data0/faser/sim/mc24/genie')
NOMINAL = {200082, 200083, 200089, 200093, 200094, 200100}


def main():
    tick = time.monotonic()
    inventory, sources = [], []
    assigned = {r['group']: r['initial_role'] for r in csv.DictReader(
        (ROOT / 'workbook/stage87_energy_ml/source_assignment.tsv').open(), delimiter='\t')}
    old_locked = {r['component'] + ':' + r['group'].split(':')[-1]
                  for r in csv.DictReader((ROOT / 'ml/configs/files.tsv').open(), delimiter='\t')
                  if r['partition'] == 'test'}
    for run in range(200080, 200102):
        directory = BASE / str(run)
        logs = sorted((directory / 'log/s0014').glob('*-HITS.sim.log'))
        evidence = []
        for path in dict.fromkeys(logs[:1] + logs[-1:]):
            text = path.read_text()
            selected = [dict(line=i + 1, text=line) for i, line in enumerate(text.splitlines())
                        if any(s in line for s in ['Input File:', 'faser_simulate.py ',
                                                  'GeoModel.FaserVersion ', 'IOVDb.GlobalTag ',
                                                  'Random.SeedOffset ', 'Release:'])]
            evidence.append(dict(path=str(path), bytes=path.stat().st_size, lines=selected))
        paths = [item['text'].split('Input File: ', 1)[1].strip()
                 for e in evidence for item in e['lines'] if 'Input File: ' in item['text']]
        evnt = paths[0] if paths else None
        assert not paths or len(set(paths)) == 1, (run, paths)
        rdos = sorted((directory / 'rdo/s0014').glob('*-RDO.root'))
        run_sources = []
        for rdo in rdos:
            segment = re.search(r'-(\d{5}-\d{5})-s0014', rdo.name)
            if not segment:
                continue
            phys = directory / 'phy/s0014' / rdo.name.replace('-RDO.root', '-PHYS.root')
            source = dict(index=len(sources), run=run, component=('charm' if 'charm' in rdo.name
                          else 'k' if re.search(r'_k-', rdo.name) else 'pi'),
                          rdo=str(rdo), input=str(phys), phys_exists=phys.is_file(),
                          segment=segment[1], EVNT=evnt, nominal=run in NOMINAL,
                          file_probability=1.0)
            group = source['component'] + ':' + source['segment']
            source.update(group=group, inherited_role=assigned.get(group, 'unassigned'),
                          old_locked=group in old_locked,
                          eligible=group in assigned and group not in old_locked)
            sources.append(source)
            run_sources.append(source['index'])
        inventory.append(dict(run=run, nominal=run in NOMINAL, EVNT=evnt,
                              EVNT_exists=bool(evnt and Path(evnt).is_file()),
                              simulation_log_N=len(logs), evidence=evidence,
                              RDO_N=len(rdos), PHYS_matched_N=sum(sources[i]['phys_exists'] for i in run_sources),
                              source_indices=run_sources))
    protocol = dict(stage=130, inventory=inventory, sources=sources,
                    scope='Only 200080-200101 exact nominal/alternative flux directories; no recursive EOS scan',
                    pilot='first sorted full parent source per alternative run; no replacement by yield or residual',
                    producer='pinned d32/FASERNU04/conditions06 official sparse RDO reco after truth-only superset; actual payload03 to01 once',
                    independence='full-depth EVNT path/entry/full-state and old incoming overlap to be checked; no blind assertion from run number',
                    guardrails='original roles and allK;typed62 raw11/pz0;original cuts pz>50;reserved zero prediction',
                    wall_s=time.monotonic() - tick)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'source_protocol.json').write_text(json.dumps(protocol, indent=2) + '\n')
    print(json.dumps([{k: v for k, v in x.items() if k not in ['evidence', 'source_indices']}
                      for x in inventory], indent=2))


if __name__ == '__main__':
    main()
