"""Read own completed compact returns, never regenerate a scientific result."""
import argparse
import json
import sys
import tarfile
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'ntuples/energy_ml_stage131';OUT=ROOT/'workbook/stage131_energy_ml'
p=argparse.ArgumentParser();p.add_argument('phase');p.add_argument('indices',nargs='*',type=int);p.add_argument('--archive',type=Path);args=p.parse_args()
phase=args.phase;indices=args.indices or [0]
assert args.archive is None or len(indices)==1
for index in indices:
    tick=time.perf_counter();parents={};exitcode=None
    archive=args.archive or CACHE/f'{phase}_{index}_result.tar.gz'
    with tarfile.open(archive) as t:
        members=t.getmembers()
        for m in members:
            assert not m.name.startswith('/') and '..' not in Path(m.name).parts
            assert m.isfile() and m.name.startswith(('workbook/stage131_energy_ml/','ntuples/energy_ml_stage131/','ml/artifacts/stage131/'))
            payload=t.extractfile(m).read();assert len(payload)==m.size
            if phase=='production':
                name=Path(m.name).name
                if name==f'{phase}_{index}_exitcode.txt':exitcode=int(payload)
                if name.startswith('parent_') and name.endswith(('_summary.json','_selection.json')):
                    _,i,kind=name.split('_',2);parents.setdefault(int(i),{})[kind[:-5]]=json.loads(payload)
            else:
                target=ROOT/m.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
                assert target.read_bytes()==payload
    if phase!='production':exitcode=int((OUT/f'{phase}_{index}_exitcode.txt').read_text())
    assert exitcode is not None
    if phase=='production':
        expected=json.loads((OUT/'production_contract.json').read_text())['batches'][index]
        assert set(expected)==set(parents)
        assert all('summary' in r for r in parents.values())
    print(phase,index,'exit',exitcode,'bytes',archive.stat().st_size)
    compact=[dict(index=i,successful=r['summary'].get('successful',False),selected_N=r.get('selection',{}).get('selected_N',0)) for i,r in sorted(parents.items())]
    (OUT/f'{phase}_{index}_transfer.json').write_text(json.dumps(dict(bytes=archive.stat().st_size,exitcode=exitcode,members=[dict(name=m.name,bytes=m.size) for m in members],parents=compact,expanded_to_EOS=phase!='production',wall_s=time.perf_counter()-tick,scope='production archive fully decompressed and member length verified; event payloads expand once on analysis-worker scratch; other phases byte-roundtrip afterwrite'),indent=2)+'\n')
