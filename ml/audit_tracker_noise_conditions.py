#!/usr/bin/env python3
"""Read the two exact SCT calibration folders used by the replay."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

from PyCool import cool

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--database', default='/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/sqlite200/ALLP200.db')
args = parser.parse_args()
start = time.perf_counter()
db = cool.DatabaseSvcFactory.databaseService().openDatabase('sqlite://;schema='+args.database+';dbname=OFLP200', True)
records = []
for run in [100049, 100050]:
    for name in ['ChipNoise', 'ChipGain']:
        folder = db.getFolder('/SCT/DAQ/Calibration/'+name)
        tag = folder.resolveTag('OFLCOND-FASER-05')
        iterator = folder.browseObjects(run<<32, run<<32, cool.ChannelSelection.all(), tag)
        rows, fields = [], {}
        while iterator.goToNext():
            obj = iterator.currentRef()
            rows.append((int(obj.channelId()), int(obj.since()), int(obj.until())))
            for key, value in dict(obj.payload()).items():
                if not isinstance(value, str):
                    continue
                numbers = [float(v) for v in value.split()]
                field = fields.setdefault(key, dict(empty_rows=0,lengths=Counter(),values=Counter()))
                field['empty_rows'] += not bool(numbers)
                field['lengths'][len(numbers)] += 1
                field['values'].update(numbers)
        iterator.close()
        records.append(dict(run=run,folder=folder.fullPath(),tag=tag,rows=len(rows),
            unique_channels=len(set(r[0] for r in rows)),iov=sorted(set((r[1],r[2]) for r in rows)),fields=fields))
db.closeDatabase()
args.output.write_text(json.dumps(dict(database=args.database,global_tag='OFLCOND-FASER-05',
    records=records,wall_s=time.perf_counter()-start),indent=2)+'\n')
