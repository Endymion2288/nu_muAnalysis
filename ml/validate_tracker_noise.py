#!/usr/bin/env python3
"""Check compact event identities, paired tables and optional archive round-trip."""
import argparse
import csv
import json
import tarfile
from pathlib import Path

import numpy as np

from analyze_tracker_noise import NAMES, THRESHOLDS, read_result

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--directory', type=Path, default=Path('ntuples/energy_ml_stage53'))
parser.add_argument('--output', type=Path, default=Path('workbook/stage53_energy_ml'))
parser.add_argument('--archive', action='store_true')
args = parser.parse_args()
sample = read_result(args.directory, 'sample.json')
assert len(sample['sources']) == 12
nominal, off, sources, pbins = [], [], [], []
names = ['sample.json']
for source in sample['sources']:
    s = source['source']
    entries = [c['entry'] for c in source['cases']]
    assert entries == sorted(set(entries))
    assert source['total_entries'] == 50000
    for arm, destination in [('nominal', nominal), ('nonoise', off)]:
        name = f'{arm}_{s}.json'; names.append(name)
        result = read_result(args.directory, name)
        assert result['mode'] == arm and result['input'] == source['input_rdo']
        assert result['requested_entries'] == entries
        assert result['original_hits_diagnostic']
        assert result['material_source'].endswith('/material-maps-alma9.json')
        assert len(result['records']) == len(source['cases'])
        for rec, case in zip(result['records'], source['cases']):
            assert (rec['run'], rec['entry'], rec['event']) == (source['run'], case['entry'], case['event'])
            original = rec['clusters']['Reference'] + [rec['spacepoints']['Reference'], rec['segments']['Reference']]
            assert original == case['original_counts']
            if arm == 'nominal':
                assert rec['rdo_p4_exact_equal'] and rec['reference_p4_idempotent']
                assert rec['tracks']['Reference'] == rec['tracks']['Replay']
                assert all(rec['selected'].values())
            destination.append(rec)
    sources.extend([s]*len(entries)); pbins.extend(c['pbin'] for c in source['cases'])
assert len(nominal) == len(off) == 2048
assert np.bincount(pbins).tolist() == [1024,1024]
sources, pbins = np.array(sources), np.array(pbins)
on = np.array([r['clusters']['Replay']+[r['spacepoints']['Replay'],r['segments']['Replay']] for r in nominal])
no = np.array([r['clusters']['Replay']+[r['spacepoints']['Replay'],r['segments']['Replay']] for r in off])
for a,b in zip(nominal,off):
    assert a['tracks']['Reference'] == b['tracks']['Reference']
groups = dict(all=np.ones(2048,bool), p100_250=pbins==0, p250_1000=pbins==1,
              mu_minus=sources<6, mu_plus=sources>=6)
groups.update({f'source{s}':sources==s for s in range(12)})
groups.update({f'source{s}_p{b}':(sources==s)&(pbins==b) for s in range(12) for b in [0,1]})
with (args.output/'paired_response.tsv').open() as f:
    table = list(csv.DictReader(f,delimiter='\t'))
assert len(table) == len(groups)*6
for row in table:
    mask = groups[row['group']]; j = NAMES.index(row['variable'])
    x,y = on[mask,j],no[mask,j]
    assert len(x) == int(row['N'])
    for key,value in dict(nominal_mean=x.mean(),nonoise_mean=y.mean(),delta_mean=(y-x).mean(),
                          delta_extra_pp=100*((y>THRESHOLDS[j]).mean()-(x>THRESHOLDS[j]).mean())).items():
        assert np.isclose(value,float(row[key]),rtol=0,atol=5e-13), (key,value,row[key])
    for label,values in [('nominal',x),('nonoise',y)]:
        for q in [16,50,84,95,99]:
            assert float(row[f'{label}_q{q}']) == np.quantile(values,q/100)
    assert int(row['same'])+int(row['decreased'])+int(row['increased']) == len(x)
with (args.output/'selection_migration.tsv').open() as f:
    migration = list(csv.DictReader(f,delimiter='\t'))
for row in migration:
    mask = groups[row['group']]
    assert sum(int(row[k]) for k in ['pass_to_pass','pass_to_fail','fail_to_pass','fail_to_fail']) == mask.sum()
    failed = sum(not off[i]['selected']['Replay'] for i in np.flatnonzero(mask))
    assert failed == int(row['pass_to_fail'])
archive_path = args.directory/'replay_results.tar.gz'
if args.archive:
    assert not archive_path.exists()
    with tarfile.open(archive_path,'w:gz') as archive:
        for name in names:
            archive.add(args.directory/name,arcname=name)
    with tarfile.open(archive_path) as archive:
        for name in names:
            assert archive.extractfile(name).read() == (args.directory/name).read_bytes()
    for name in names:
        (args.directory/name).unlink()
for name in names:
    assert read_result(args.directory,name)
result = dict(events=2048,sources=12,pbin_counts=np.bincount(pbins).tolist(),
              table_rows=len(table),selection_groups=len(migration),
              identity_and_nominal_gate=True,paired_tables_independently_recomputed=True,
              archive_bytes=archive_path.stat().st_size if archive_path.exists() else None,
              archive_byte_roundtrip=args.archive)
(args.output/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
