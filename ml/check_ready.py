#!/usr/bin/env python3
"""DAG PRE gate: defer (75) until every atomically published shard is present."""
import argparse
import csv
import json
import socket
import time
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--manifest',type=Path,required=True)
args=p.parse_args()
rows=list(csv.DictReader(args.manifest.open(),delimiter='\t'))
base=Path(rows[0]['cache']).parents[1]
if all((base/'dataset'/f'{part}.npz').exists() for part in ['train','validation','calibration','test','challenge']):
    print('Consolidated partitions ready',flush=True)
else:
    # One directory listing avoids hundreds of cached negative EOS lookups.
    available={p.name for p in (base/'shards').iterdir()} if (base/'shards').exists() else set()
    missing=[r['index'] for r in rows if Path(r['cache']).name not in available]
    status=dict(host=socket.gethostname(),time=time.time(),complete=len(rows)-len(missing),total=len(rows),missing=missing)
    (args.manifest.resolve().parents[2]/'logs/ml_ready_status.json').write_text(json.dumps(status)+'\n')
    print(f'Extraction complete {len(rows)-len(missing)}/{len(rows)}; missing {missing[:8]}',flush=True)
    if missing:raise SystemExit(75)
