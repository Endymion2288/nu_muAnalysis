#!/usr/bin/env python3
"""Verify source shards against the single cache before removing duplicates."""
import csv,gzip,json
from pathlib import Path
import numpy as np

repo=Path(__file__).resolve().parents[1];cache=repo/'ntuples/energy_ml_stage55';out=repo/'workbook/stage55_energy_ml'
assert json.loads((out/'validation.json').read_text())['formal_fits']==15
rows=list(csv.DictReader((repo/'ml/configs/low_energy_files.tsv').open(),delimiter='\t'))
excluded=json.loads((repo/'ml/configs/low_energy.json').read_text()).get('excluded_source_indices',[])
rows=[r for r in rows if int(r['index']) not in excluded]
with np.load(cache/'dataset.npz') as z:d={k:z[k] for k in z.files if k!='metadata_json'}
metadata=[];remove=[]
for r in rows:
 path=cache/f"shards/{r['index']}.npz";take=np.flatnonzero(d['source']==int(r['index']))
 with np.load(path) as z:
  metadata.append(json.loads(str(z['metadata_json'])))
  for k in z.files:
   if k!='metadata_json':np.testing.assert_array_equal(z[k],d[k][take])
 remove.append(path)
archive=cache/'extraction_metadata.json.gz'
with gzip.open(archive,'wt') as f:json.dump(metadata,f,separators=(',',':'))
with gzip.open(archive,'rt') as f:assert json.load(f)==metadata
removed_bytes=sum(p.stat().st_size for p in remove)
for p in remove:p.unlink()
# Store shared calibration/evaluation rows once instead of fifteen copies of
# large training-index arrays; preserve every seed prediction and fit metadata.
cfg=json.loads((repo/'ml/configs/low_energy.json').read_text())
seed_eval=[];seed_cal=[];training_metadata=[];seed_paths=[]
for name in cfg['candidates']:
 ep=[];cp=[]
 for seed in cfg['seed_indices']:
  path=repo/f'ml/artifacts/stage55/{name}/{seed}/predictions.npz'
  with np.load(path) as z:
   ep.append(z['eval_raw_log']);cp.append(z['cal_raw_log'])
   training_metadata.append(json.loads(str(z['metadata_json'])))
   ev=z['eval_row'];cal=z['cal_row']
  seed_paths.append(path)
 seed_eval.append(ep);seed_cal.append(cp)
seed_data=dict(model_names=np.array(cfg['candidates']),eval_row=ev,cal_row=cal,
               eval_raw_log=np.asarray(seed_eval),cal_raw_log=np.asarray(seed_cal))
np.savez_compressed(cache/'seed_predictions.npz',**seed_data)
with np.load(cache/'seed_predictions.npz') as z:
 for k,v in seed_data.items():np.testing.assert_array_equal(z[k],v)
(out/'training_metadata.json').write_text(json.dumps(training_metadata,indent=2)+'\n')
removed_bytes+=sum(p.stat().st_size for p in seed_paths)
for p in seed_paths:p.unlink()
# The transport archive is redundant after all persisted models were reloaded.
for transport in [cache/'models.tar.gz',repo/'software/energy-ml-low-energy-stage55.tar.gz',repo/'software/energy-ml-low-energy-train-stage55.tar.gz']:
 if transport.exists():removed_bytes+=transport.stat().st_size;transport.unlink()
retained=[p for p in cache.rglob('*') if p.is_file()]+[p for p in (repo/'ml/artifacts/stage55').rglob('*') if p.is_file()]
result=dict(source_shards_verified_and_removed=len(remove),duplicate_bytes_removed=removed_bytes,retained_bytes=sum(p.stat().st_size for p in retained),retained_files=len(retained),files=[dict(path=str(p.relative_to(repo)),bytes=p.stat().st_size) for p in retained])
(out/'storage.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='files'}))
