"""Actual per-target-run cabling, only explicit frozen runs."""
import json
from pathlib import Path
from PyCool import cool
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage175_energy_ml'
plan=json.loads((ROOT/'workbook/stage129_energy_ml/extraction_contract.json').read_text())
path=Path('/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/sqlite200/CABP200.db').resolve()
db=cool.DatabaseSvcFactory.databaseService().openDatabase(f'sqlite://;schema={path};dbname=OFLP200',True)
f=db.getFolder('/WAVE/DAQ/CableMapping');tag=f.resolveTag('OFLCOND-FASER-05');rows=[]
for run in sorted({s['run'] for s in plan['requests']}):
    channels=[]
    for obj in f.browseObjects(run<<32,run<<32,cool.ChannelSelection(0,63),tag):
        v=obj.payload()
        if v['type']=='trigger':channels.append(dict(hardware=int(obj.channelId()),since=int(obj.since()),until=int(obj.until()),payload={str(k):v[k] for k in v.keys()}))
    channels.sort(key=lambda r:r['hardware']);good=[c['hardware'] for c in channels]==[8,9,10,11]
    if good:
        for i,j in [(0,1),(2,3)]:
            a,b=channels[i]['payload'],channels[j]['payload'];good=good and all(a[k]==b[k] for k in ['type','station','plate']) and a['pmt']!=b['pmt']
    rows.append(dict(run=run,path=str(path),resolved_tag=tag,channels=channels,supported=good))
db.closeDatabase();(OUT/'cable_mapping.json').write_text(json.dumps(rows,indent=2)+'\n')
