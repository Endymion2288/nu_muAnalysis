"""Fixed original first64 PHYS parents, with full-index key multiplicity."""
import json
import resource
import time
from collections import Counter
from pathlib import Path
import uproot

out=Path('workbook/stage160_energy_ml')
plan=json.loads((out/'protocol.json').read_text())
tick,cpu=time.perf_counter(),time.process_time()
with uproot.open(plan['PHYS'],array_cache=None) as source:
    tree=source['nt'];index=tree.arrays(['run','eventID'],library='np')
    counts=Counter(zip(index['run'].tolist(),index['eventID'].tolist()))
    stamp=tree.arrays(['eventTime'],entry_stop=64,library='np')['eventTime']
    records=[dict(PHYS_entry=i,run=int(index['run'][i]),event=int(index['eventID'][i]),timestamp=int(stamp[i]),
                  PHYS_key_multiplicity=counts[(int(index['run'][i]),int(index['eventID'][i]))]) for i in range(64)]
    report=dict(records=records,PHYS=plan['PHYS'],PHYS_N=int(tree.num_entries),read_bytes=int(source.file.source.num_requested_bytes),
                CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
(out/'targets.json').write_text(json.dumps(report,indent=2)+'\n')
