"""Batch-only measured throughput and scalar archive inventory after full audit."""
import json
from pathlib import Path
from stage158_finalize import gnu
from stage186_common import OUT,ROOT,CACHE,ART,table,write
if __name__=='__main__':
 summaries=[json.loads((OUT/f'full_{g}_summary.json').read_text()) for g in range(35)];groups=[];sources=[]
 for g,s in enumerate(summaries):
  complete=gnu(OUT/f'full_{g}_time.txt') if (OUT/f'full_{g}_time.txt').exists() else None
  groups.append(dict(group=g,N=s['N'],source_N=s['source_N'],internal_CPU_s=s['CPU_s'],internal_wall_s=s['wall_s'],ROOT_requested_B=s['ROOT_requested_B'],RSS_KiB=s['RSS_KiB'],startup_CPU_s=s['startup_CPU_s'],first_execute_CPU_s=s['event_resources'][0]['CPU_s']))
  for r in s['sources']:
   ev=[e for e in s['event_resources'] if e['source_index']==r['index']];sources.append(dict(index=r['index'],group=g,N=r['N'],execute_CPU_s=sum(e['CPU_s'] for e in ev),ROOT_event_requested_B=sum(e['ROOT_requested_B'] for e in ev),first_execute_CPU_s=ev[0]['CPU_s'],mapping_channel_N=len(r['mappings'])))
 table('production_group_resources.tsv',groups);table('production_source_resources.tsv',sources)
 (OUT/'source_physical_maps.json').write_text(json.dumps([dict(group=g,**r) for g,s in enumerate(summaries) for r in s['sources']],separators=(',',':'))+'\n')
 files=list(CACHE.glob('*.npz'))+list(ART.glob('*'));total=sum(f.stat().st_size for f in files)
 attempts=[]
 for path in sorted(OUT.glob('*_driver.json')):
  if not path.name.startswith(('production_','repair_')):continue
  attempts += [dict(phase=path.stem.removesuffix('_driver'),**r) for r in json.loads(path.read_text())]
 assert sum(r['exit']==0 for r in attempts)==len(summaries)
 table('production_reader_attempts.tsv',attempts)
 write('successful_reader_totals.json',dict(parents_N=sum(s['N'] for s in summaries),sources_N=sum(s['source_N'] for s in summaries),old_raw11_controls_N=sum(s['raw11_old_feature_checks_N'] for s in summaries),successful_reader_internal_CPU_s=sum(s['CPU_s'] for s in summaries),parents_per_successful_internal_CPU_s=sum(s['N'] for s in summaries)/sum(s['CPU_s'] for s in summaries),successful_reader_wall_s=sum(s['wall_s'] for s in summaries),parents_per_summed_successful_reader_wall_s=sum(s['N'] for s in summaries)/sum(s['wall_s'] for s in summaries),note='Successful readers only; all failed attempts and transport/setup CPU remain in final scheduler/budget accounting. These throughput measures are not a controlled parallel speedup.'))
 write('resource_validation.json',dict(passed=total<=67108864,full_parents_N=sum(s['N'] for s in summaries),successful_full_Athena_readers_N=len(summaries),full_reader_attempts_N=len(attempts),failed_full_reader_attempts_N=sum(r['exit']!=0 for r in attempts),full_internal_CPU_s=sum(s['CPU_s'] for s in summaries),full_ROOT_requested_B=sum(s['ROOT_requested_B'] for s in summaries),sum_internal_reader_wall_s=sum(s['wall_s'] for s in summaries),peak_single_reader_RSS_KiB=max(s['RSS_KiB'] for s in summaries),current_scientific_array_model_B=total,cap_B=67108864,physical_network_IO='unmeasured; ROOTrequested is logical librarybytes',controlled_speedup='unmeasured',GPU=0,allocated_CPUs_per_job=8,max_reader_processes_per_job=8,max_concurrent_jobs=4,overall_complete=False))
 assert total<=67108864
