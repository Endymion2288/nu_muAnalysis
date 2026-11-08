import sys
from stage193_common import *
phase=sys.argv[1];cpu=time.process_time();tick=time.perf_counter()
rows,slow=build(phase);CACHE.mkdir(exist_ok=True)
with gzip.open(CACHE/f'{phase}_parents.json.gz','wt') as f:json.dump(rows,f,separators=(',',':'),allow_nan=False)
summary=summaries(rows);write(f'{phase}_accounting.json',dict(N=len(rows),groups=summary))
flat=[]
for r in rows:
 for k,v in r['classes'].items():flat.append({key:value for key,value in r.items() if key!='classes'}|dict(deposit_class=k,**v))
table(f'{phase}_parents.tsv',flat)
write(f'{phase}_summary.json',dict(passed=True,N=len(rows),CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
 RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,slowest_parent_CPU_s=slow))
if phase=='pilot':
 # A conservative thirty complete pilot process costs plus a further per-parent term.
 # process_time includes Python imports/startup for this complete scalar pilot.
 complete=time.process_time();projection=30*complete+3*160*slow
 write('admission.json',dict(admitted=bool(projection<=100 and complete+projection+100<=300 and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1.25/1024<=4000),
  projection_CPU_s=projection,complete_process_CPU_s=complete,slowest_parent_CPU_s=slow,full_cap_CPU_s=100,audit_CPU_s=100,overall_complete=False))
print('COMPLETE',phase,len(rows),flush=True)
