"""Eight allocated reader processes maximum, separate logs and complete timing."""
import concurrent.futures,json,subprocess,sys
from pathlib import Path
OUT=Path('workbook/stage186_energy_ml');p=json.loads((OUT/'protocol.json').read_text())
def run(task):
 script,args,label=task
 with (OUT/f'{label}.log').open('w') as stream:
  r=subprocess.run(['/usr/bin/time','-v','-o',str(OUT/f'{label}_time.txt'),sys.executable,'-u','ml/'+script,*map(str,args)],stdout=stream,stderr=subprocess.STDOUT)
 print(label,'exit',r.returncode,flush=True)
 if r.returncode:print((OUT/f'{label}.log').read_text()[-12000:],flush=True)
 return dict(label=label,exit=r.returncode)
if __name__=='__main__':
 phase=sys.argv[1]
 if phase=='pilot_repair':phase='pilot'
 if phase=='pilot':tasks=[('stage186_native.py',['pilot',0],'pilot_0'),('stage186_controls.py',[],'input_controls')]
 elif phase=='pilot_audit':tasks=[('stage186_native.py',['repeat',0],'repeat_0')]
 else:
  job=int(phase.split('_')[1]);groups=json.loads((OUT/f'{phase}_plan.json').read_text())['groups'] if phase.startswith('repair_') else p['production_jobs'][job]
  tasks=[('stage186_native.py',['full',g],f'full_{g}') for g in groups]
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:result=list(pool.map(run,tasks))
 (OUT/f'{phase}_driver.json').write_text(json.dumps(result,indent=2)+'\n');assert all(r['exit']==0 for r in result)
 if phase=='pilot_audit':
  import numpy as np
  with np.load('ntuples/energy_ml_stage186/pilot_0.npz') as z:a={k:z[k] for k in z.files}
  with np.load('ntuples/energy_ml_stage186/repeat_0.npz') as z:b={k:z[k] for k in z.files}
  ix=np.searchsorted(a['row'][:40],b['row'])
  for k in b:np.testing.assert_array_equal(a[k][ix],b[k])
  s=json.loads((OUT/'pilot_0_summary.json').read_text());literal=s['literal_checks']
  result=dict(passed=True,pilot_parents_N=s['N'],source_N=s['source_N'],repeat_parents_N=len(ix),repeat_all_fields_exact=True,literal_checks_N=len(literal),max_abs_literal_delta_pC=max(r['abs_delta_pC'] for r in literal),max_tolerance_fraction=max(r['abs_delta_pC']/r['tolerance_pC'] for r in literal),input_controls_passed=json.loads((OUT/'input_controls.json').read_text())['passed'],energy_fits=0,new_G4=0,overall_complete=False)
  (OUT/'pilot_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)

  assert subprocess.run([sys.executable,"ml/stage186_admit.py"]).returncode==0
