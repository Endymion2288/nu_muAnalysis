"""Exact per-run source cable metadata, in the pinned Athena environment."""
import json
from pathlib import Path
from PyCool import cool
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage174_energy_ml'
p=json.loads((OUT/'protocol.json').read_text());base=Path('/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/sqlite200/CABP200.db').resolve();rows=[]
for source in p['sources']:
    record=dict(label=source['label'],path=str(base),run=source['run'],supported=False,channels=[])
    db=None
    try:
        instance='CONDBR3' if source['kind']=='data' else 'OFLP200';tag='' if source['kind']=='data' else 'OFLCOND-FASER-05'
        db=cool.DatabaseSvcFactory.databaseService().openDatabase(f'sqlite://;schema={base};dbname={instance}',True)
        f=db.getFolder('/WAVE/DAQ/CableMapping');resolved=f.resolveTag(tag) if tag and f.versioningMode()==cool.FolderVersioning.MULTI_VERSION else ''
        for obj in f.browseObjects(source['run']<<32,source['run']<<32,cool.ChannelSelection(0,63),resolved):
            v=obj.payload()
            if v['type']=='trigger':record['channels'].append(dict(hardware=int(obj.channelId()),since=int(obj.since()),until=int(obj.until()),payload={str(k):v[k] for k in v.keys()}))
        record.update(instance=instance,resolved_tag=resolved,supported=True)
    except Exception as error:record['error']=str(error)
    finally:
        if db is not None:db.closeDatabase()
    record['channels'].sort(key=lambda r:r['hardware']);rows.append(record)
(OUT/'cable_mapping.json').write_text(json.dumps(rows,indent=2)+'\n')
