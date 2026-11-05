"""Read per-run actual COOL payloads; no residual-fitted calibration."""
import argparse
import json
from pathlib import Path

from PyCool import cool

p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);p.add_argument('--output',required=True);a=p.parse_args()
path=Path('/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/sqlite200/ALLP200.db')
db=cool.DatabaseSvcFactory.databaseService().openDatabase(f'sqlite://;schema={path};dbname=OFLP200',True)
folder=db.getFolder('/WAVE/Calibration/MIP_ref');result=dict(run=a.run,database=str(path.resolve()),resolved=str(folder.resolveTag('OFLCOND-FASER-06')),payloads={})
for tag in ['WAVE-Calibration-01-LG','WAVE-Calibration-03-LG']:
    rows=[]
    for obj in folder.browseObjects(a.run<<32,(a.run<<32)+1,cool.ChannelSelection.all(),tag):
        if obj.channelId() in range(4):rows.append(dict(channel=int(obj.channelId()),since=int(obj.since()),until=int(obj.until()),charge_ref=float(obj.payload()['charge_ref'])))
    assert len(rows)==4;result['payloads'][tag]=rows
db.closeDatabase();Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
