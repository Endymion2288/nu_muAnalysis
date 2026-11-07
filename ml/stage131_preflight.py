"""Same fixed first pilot parent, full small-sample instrument validation."""
import gzip
import json
from stage131_pilot import OUT,CACHE,worker
with gzip.open(CACHE/'frame.json.gz','rt') as f:frame=json.load(f)
result=worker(frame[50])
(OUT/'preflight_results.json').write_text(json.dumps(result,indent=2)+'\n')
