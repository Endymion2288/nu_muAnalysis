#!/usr/bin/env python3
import argparse
import csv
import json
import re
from pathlib import Path
parser=argparse.ArgumentParser(description='Validate three-way covariance report closure and links')
parser.add_argument('--report',type=Path,default=Path('workbook/stage210_covariance/full'))
args=parser.parse_args()
out=args.report
def read(name):return list(csv.DictReader((out/(name+'.tsv')).open(),delimiter='\t'))
s=json.loads((out/'summary.json').read_text());checks={}
for v in s['versions']:
 for m,mode in enumerate(['forward','backward','merge']):
  eff=[r for r in read('efficiency') if r['version']==v and r['mode']==mode and r['group']=='all' and r['denominator_name']=='truth_station_acceptance']
  for stage,key in [('final','accepted_final'),('final_correct','accepted_final_correct')]:
   r=next(r for r in eff if r['stage']==stage)
   assert int(r['passed'])==s[key][v][m]
   assert int(r['passed'])+int(r['failed'])==140132
  failed=[r for r in read('first_failed_cut') if r['version']==v and r['mode']==mode and r['group']=='all']
  assert sum(int(r['events']) for r in failed)==140132-s['accepted_final'][v][m]
checks['efficiency_first_failure_closure']=True
for r in read('paired_efficiency'):
 if r['denominator']=='0':continue
 assert int(r['after'])-int(r['before'])==int(r['gained'])-int(r['lost'])
checks['paired_efficiency_closure']=True
for r in read('version_loss_causes'):
 rows=[x for x in read('version_loss_causes') if all(x[k]==r[k] for k in ['baseline','variant','mode','migration'])]
 assert sum(int(x['events']) for x in rows)==int(r['total'])
checks['migration_categories_close']=True
for r in read('paired_track_properties'):
 n=int(r['pairs'])
 for prop in ['measurements','layers','ndof']:
  assert sum(int(r[prop+'_'+k]) for k in ['fewer','equal','more'])==n
 assert int(r['charge_disagreements'])==int(r['wrong_to_right_charge'])+int(r['right_to_wrong_charge'])
checks['paired_track_property_closure']=True
for r in read('numerical_and_charge'):
 if r['scope']=='final':
  assert all(int(r[k])==0 for k in ['nonfinite_chi2','nonpositive_ndof','nonfinite_pz'])
checks['final_numerical_validity']=True
for r in read('full_input_cutflow'):
 if r['cut']=='Truth pz > 100 GeV':assert int(r['passed'])==383670
 if r['cut']=='NoCuts':assert int(r['passed'])==3374987
checks['full_input_cutflow']=True
for md in [Path('workbook/2026-11-14_stage210_covariance-comparison.md'),out/'detailed_results.md']:
 for link in re.findall(r'\]\(([^)]+)\)',md.read_text()):
  if link.startswith(('http','app:','#')):continue
  assert (md.parent/link).exists(),(str(md),link)
checks['report_links_exist']=True
checks['report_archive_bytes']=244828160
Path('workbook/stage210_covariance/final_validation.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks))
