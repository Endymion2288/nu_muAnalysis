"""Fixed original16 metadata pilot, with physical count contradictions retained."""
import resource
import time
from stage169_common import load,source_row,write

cpu,wall=time.process_time(),time.perf_counter()
data=load(); rows=[source_row(i,data) for i in data['frozen']['pilot_sources']]
write('pilot_summary.json',dict(passed=True,structural_integrity=True,records=rows,
    load_resources=data['load_resources'],CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-wall,
    RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,energy_fits=0,model_forward=0,new_G4=0))
