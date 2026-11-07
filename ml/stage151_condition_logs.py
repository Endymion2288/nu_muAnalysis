"""Compact actual resolved condition tags from existing execution text logs."""
import json
import re
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage151_energy_ml'


def parse(text):
    rows = re.findall(r'HVS tag (\S+) resolved to (\S+) for folder (\S+)', text)
    return dict(global_tags=sorted(set(re.findall(r'Global tag: (\S+)', text))),
                folders=[dict(global_tag=a, resolved_tag=b, folder=c) for a, b, c in dict.fromkeys(rows)])


def main():
    result = dict(nominal06={}, current04={})
    source = ROOT/'software/stage149/worker_logs.tar.gz'
    with tarfile.open(source, 'r:gz') as archive:
        for step in ['digi', 'reco', 'native']:
            name = f'workbook/stage149_energy_ml/full/{step}.log'
            result['nominal06'][step] = dict(source=f'{source.relative_to(ROOT)}:{name}',
                **parse(archive.extractfile(name).read().decode(errors='replace')))
    for phase in ['pilot', 'full']:
        paths = {step: OUT/phase/(step+'.log') for step in ['digi', 'reco', 'native']}
        if all(path.exists() for path in paths.values()):
            result['current04'][phase] = {step: dict(source=str(path.relative_to(ROOT)), **parse(path.read_text(errors='replace')))
                                          for step, path in paths.items()}
    result['scope'] = 'Actual log-reported resolved tags; missing folders are not inferred; no numeric payload or physical uncertainty calculation'
    (OUT/'resolved_conditions.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Resolved-tags text audit:', list(result['current04']))


if __name__ == '__main__':
    main()
