"""Batch-only diagnosis of failed exact controls; no physics fit or tolerance changes."""
import json,subprocess,sys
from pathlib import Path
import ROOT as R
from stage184_freeze import hit_paths
OUT=Path('workbook/stage186_energy_ml');p=json.loads((OUT/'protocol.json').read_text());req=json.loads(Path('workbook/stage129_energy_ml/extraction_contract.json').read_text())['requests'];records=[]
for i in p['pilot']['source_indices']:
 s=req[i];counts=[]
 for path in hit_paths(s):
  f=R.TFile.Open(path);assert f and not f.IsZombie();t=f.Get('CollectionTree');counts.append(dict(path=path,N=int(t.GetEntries()) if t else 0));f.Close()
 f=R.TFile.Open(s['rdo']);assert f and not f.IsZombie();rdoN=int(f.Get('CollectionTree').GetEntries());f.Close()
 record=dict(index=i,declared_parent_N=s['parent_N'],actual_HITS_N=sum(c['N'] for c in counts),actual_RDO_N=rdoN,HITS=counts);records.append(record);print(record,flush=True)
(OUT/'metadata_diagnosis.json').write_text(json.dumps(records,indent=2)+'\n')
assert subprocess.run([sys.executable,'ml/stage186_controls.py','--diagnostic']).returncode==0
