#!/usr/bin/env python3
"""Bounded production-log evidence for the frozen CaloNu muon input manifest."""
import re
from pathlib import Path

from calonu_muon_control import manifest, output_dir, write_json


def evidence(path, kind):
    if not path.exists():
        return dict(path=str(path), kind=kind, measured=False)
    lines = path.read_text(errors='replace').splitlines()
    pattern = r'Remaining:|using release|Global tag:|FASER verions:|INFO.*(?:Norm:|Mean:|Sigma:|Alpha:|N:)|HVS tag.*(?:MIP_ref|Digitization)|randomSeed'
    selected = [s.strip() for s in lines if re.search(pattern, s)]
    return dict(path=str(path), kind=kind, measured=True, evidence=selected)


def main():
    repo = Path(__file__).resolve().parents[1]
    rows = []
    for row in manifest(repo):
        path = Path(row['input'])
        run = int(row['run'])
        if row['sample'] == 'MC':
            folder = path.parents[2]/'log/s0015'
            start = int(row['group'].split('_')[1].split('-')[0])
            stem = path.name.split(str(run)+'-')[0]+str(run)+'-'
            record = evidence(folder/f'{stem}{start//5:04}-PHYS.ntp.log', 'MC slice-index log reference, not proof of actual bck maker')
            record['backward_explicit_in_reference'] = any('--backward' in line for line in record.get('evidence', []))
            rows.append(record)
            rows.append(evidence(folder/f'{stem}{start:05}.gen.log', 'representative generator seed name'))
        else:
            start = int(path.name.split(f'{run:06}-')[1].split('-')[0])
            folder = Path('/eos/experiment/faser/data0/phys/2024_back/r0022_log')/f'{run:06}'
            rows.append(evidence(folder/f'Faser-Physics-{run:06}-{start//50:04}-PHYS.ntp.log', 'data ntuple reference'))
    for run in [100049,100050]:
        folder = Path('/eos/experiment/faser/sim/mc24/particle_gun')/str(run)/'log/s0015'
        rows.append(evidence(sorted(folder.glob('*RDO-merge-0.rdo.log'))[0], 'MC digitization reference'))
        rows.append(evidence(sorted(folder.glob('*00000-00004-RDO.rec.log'))[0], 'MC reconstruction reference'))
    for run in [15838,16000,16923]:
        folder = Path('/eos/experiment/faser/data0/rec/2024/r0022_log')/f'{run:06}'
        rows.append(evidence(sorted(folder.glob('*.rec.log'))[0], 'data reconstruction reference'))
    write_json(output_dir(repo)/'production_audit.json', dict(records=rows,
        limitations=['log references are not a proof of complete conditions/HV equivalence',
                     'MC100050 references 0020/0040/0059 lack backward; exact bck maker not certified for these three inputs',
                     'Different generator seed filenames and event fingerprints do not prove full flux-library genealogy independence']))
    print(dict(records=len(rows), missing=sum(not r['measured'] for r in rows)))


if __name__ == '__main__':
    main()
