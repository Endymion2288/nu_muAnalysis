import sys,json
from pathlib import Path
sys.path.insert(0,'ml')
import uproot
from audited_features import REPO,SCINTILLATORS
from track_response import TRACK_BRANCHES
from support_augmentation import save,begin,resources
out=REPO/'workbook/stage81_energy_ml';p=json.loads((out/'source_plan.json').read_text());rows=[];tick=begin()
for s in p['sources']:
 with uproot.open(s['input']) as f:
  t=f['nt'];keys=set(t.keys());required=['run','eventID','Track_PropagationError','Track_isForward']+TRACK_BRANCHES+[d+'_'+k for d in SCINTILLATORS for k in ['raw_charge','charge','status']]+[f'Calo{i}_{k}' for i in range(4) for k in ['charge','status','E_EM']]
  missing=sorted(set(required)-keys)
  rows.append(dict(index=s['index'],N=t.num_entries,branch_N=len(keys),missing_required=missing,header_requested_bytes=int(f.file.source.num_requested_bytes),branches=sorted(keys)))
save(out/'headers.json',dict(records=rows,events_read=0,**resources(tick)))
print(json.dumps([{k:v for k,v in r.items() if k!='branches'} for r in rows],indent=2))
