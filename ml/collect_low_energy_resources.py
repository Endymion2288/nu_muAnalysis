#!/usr/bin/env python3
"""Parse actual stage timings and known Condor process logs, without EOS scans."""
import ast,csv,json,re
from pathlib import Path
from train_bdt import write_table

repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage55_energy_ml'
spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage55/logs')
sub=json.loads((out/'submissions.json').read_text());batches=[('extract',sub['existing_extract']['cluster'],257),('pilot',sub['first_alternative']['cluster'],1),('pilot',sub['corrected_pilot']['cluster'],1),('reco',sub['alternative_formal']['cluster'],44)]
records=[];diagnostics=[]
pattern=re.compile(r'^(reco|ntuple|copy_rdo|extract) wall_s=([\d.]+) (?:cpu_user_s|user_s)=([\d.]+) (?:cpu_system_s|system_s)=([\d.]+) rss_KiB=(\d+)',re.M)
for mode,cluster,n in batches:
 for proc in range(n):
  stdout=(spool/f'{mode}.{cluster}.{proc}.out').read_text();stderr=(spool/f'{mode}.{cluster}.{proc}.err').read_text()
  md=next((json.loads(line) for line in stdout.splitlines() if line.startswith('{"index":')),None)
  failed=md is None
  if failed:
   assert cluster==sub['first_alternative']['cluster']
   md=dict(index=257,raw_N=10000)
  for stage,wall,user,system,rss in pattern.findall(stdout+'\n'+stderr):records.append(dict(cluster=cluster,proc=proc,index=md['index'],raw_N=md['raw_N'],stage=stage,wall_s=float(wall),user_s=float(user),system_s=float(system),cpu_s=float(user)+float(system),rss_KiB=int(rss),role='technical-failure' if failed else '100-event-pilot' if md['raw_N']==100 else 'formal'))
  for line in stdout.splitlines():
   if line.startswith('log='):
    fpe=re.search(r'FPE_totals=(\{[^}]*\})',line);levels=re.search(r'levels=(\{[^}]*\})',line)
    diagnostics.append(dict(cluster=cluster,proc=proc,index=md['index'],raw_N=md['raw_N'],stage=line.split()[0][4:],levels=json.dumps(ast.literal_eval(levels.group(1))) if levels else '',FPE=json.dumps(ast.literal_eval(fpe.group(1))) if fpe else ''))
write_table(out/'pipeline_resources.tsv',records);write_table(out/'production_diagnostics.tsv',diagnostics)
summary=[]
for role in ['formal','100-event-pilot','technical-failure']:
 for stage in ['copy_rdo','reco','ntuple','extract']:
  rr=[r for r in records if r['role']==role and r['stage']==stage]
  if rr:summary.append(dict(role=role,stage=stage,timed_processes=len(rr),wall_sum_s=sum(r['wall_s'] for r in rr),cpu_sum_s=sum(r['cpu_s'] for r in rr),max_rss_KiB=max(r['rss_KiB'] for r in rr)))
write_table(out/'pipeline_summary.tsv',summary)
print(json.dumps(summary,indent=2))
