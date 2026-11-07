"""Eight independent natural-parent full chains per allocated eight-core job."""
import concurrent.futures
import gzip
import json
import sys
from stage131_pilot import ROOT,OUT,CACHE,worker

index=int(sys.argv[1]);contract=json.loads((OUT/'production_contract.json').read_text())
with gzip.open(CACHE/'frame.json.gz','rt') as f:frame=json.load(f)
indices=contract['batches'][index];results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    tasks={pool.submit(worker,frame[i]):i for i in indices}
    for future in concurrent.futures.as_completed(tasks):
        i=tasks[future]
        try:results.append(future.result())
        except Exception as e:results.append(dict(index=i,successful=False,error=repr(e)))
(OUT/f'production_results_{index}.json').write_text(json.dumps(results,indent=2)+'\n')
assert all(r['successful'] for r in results),results
