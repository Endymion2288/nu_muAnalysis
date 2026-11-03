#!/usr/bin/env python3
"""Read only the actual MC calibration payloads used in the stage70 audit."""
from PyCool import cool
import argparse
from pathlib import Path
import json
root=Path('/cvmfs/faser.cern.ch/repo/sw/database/DBRelease/current/sqlite200/ALLP200.db')
svc=cool.DatabaseSvcFactory.databaseService();db=svc.openDatabase(f'sqlite://;schema={root};dbname=OFLP200',True);f=db.getFolder('/WAVE/Calibration/MIP_ref')
tags=list(map(str,f.listTags()));chosen=[t for t in tags if any(x in t for x in ['-01-LG','-03-LG'])];rows=[]
for tag in chosen:
 for run in [200080,200081,200082]:
  vals=[]
  for obj in f.browseObjects(run<<32,(run<<32)+1,cool.ChannelSelection.all(),tag):
   if obj.channelId() in [0,1,2,3,12,13]:
    payload=obj.payload();vals.append(dict(channel=int(obj.channelId()),since=int(obj.since()),until=int(obj.until()),payload={str(k):(payload[k] if isinstance(payload[k],(str,int,float,bool,type(None))) else str(payload[k])) for k in payload.keys()}))
  rows.append(dict(tag=tag,run=run,rows=vals))
resolved=str(f.resolveTag('OFLCOND-FASER-06'));db.closeDatabase()
r=dict(database=str(root),resolved_database=str(root.resolve()),folder='/WAVE/Calibration/MIP_ref',global_tag='OFLCOND-FASER-06',resolved_tag=resolved,listed_tags=tags,measurements=rows,scope='current local MC conditions; not a proof of the original F7 production snapshot',source_formula='CaloRecTool::reconstruct E_EM=charge_pC/MIPcharge_ref*330MeV for MC without gain correction')
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'workbook/stage70_energy_ml/calo_conditions_qa.json')
args=p.parse_args()
args.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
