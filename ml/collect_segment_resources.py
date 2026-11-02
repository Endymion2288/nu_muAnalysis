#!/usr/bin/env python3
"""Read the known stage51 Condor logs only; no broad history or source scan."""
import json
import re
from pathlib import Path
from segment_information import OUT
spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage51/logs');records=[]
for cluster,count,phase in [(13646667,9,'extract'),(13646672,1,'train')]:
    for proc in range(count):
        path=spool/f'{cluster}.{proc}.err';assert path.is_file(),path
        text=path.read_text()
        matches=re.findall(r'stage51_(extract|train) wall_s=([0-9.]+) max_rss_KiB=([0-9]+) user_s=([0-9.]+) system_s=([0-9.]+)',text)
        assert len(matches)==(1 if phase=='extract' else 3),(path,text[-2000:])
        for j,(kind,wall,rss,user,system) in enumerate(matches):records.append(dict(cluster=cluster,proc=proc,phase=kind,fold=j if phase=='train' else None,wall_s=float(wall),max_rss_KiB=int(rss),user_s=float(user),system_s=float(system)))
(OUT/'execution_resources.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records))
