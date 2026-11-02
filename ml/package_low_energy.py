#!/usr/bin/env python3
"""Package the fixed stage55 extractor and existing analysis binary, no rebuild."""
import csv,json,tarfile
from pathlib import Path
repo=Path(__file__).resolve().parents[1]
paths=['build/analysis','build/libAnalysis.so','AnalysisZipFramework/config','AnalysisZipFramework/include',
       'AnalysisZipFramework/submission/validate_merge_ntuple.py','setup_env.sh',
       'ml/extract_low_energy.py','ml/frozen_evaluation.py','ml/track_response.py','ml/train_bdt.py',
       'ml/configs/low_energy_files.tsv','ml/configs/low_energy.json','ml/configs/baseline.yaml','ml/configs/track_response.yaml']
# analysis is linked to libAnalysis, discover exact existing filename.
paths=[p for p in paths if (repo/p).exists()]
paths += [str(p.relative_to(repo)) for p in (repo/'build').glob('*.so') if str(p.relative_to(repo)) not in paths]
archive=repo/'software/energy-ml-low-energy-stage55.tar.gz'
with tarfile.open(archive,'w:gz',compresslevel=1) as tar:
 for path in paths:tar.add(repo/path,arcname=path)
spool=Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage55');spool.mkdir(exist_ok=True)
worker=(repo/'AnalysisZipFramework/submission/run_ml_low_energy.sh').read_bytes()
worker_path=spool/'worker_v2.sh'
if worker_path.exists():
 assert worker_path.read_bytes()==worker,'Use a new immutable worker version for changed code'
else:worker_path.write_bytes(worker)
rows=list(csv.DictReader((repo/'ml/configs/low_energy_files.tsv').open(),delimiter='\t'))
excluded=json.loads((repo/'ml/configs/low_energy.json').read_text()).get('excluded_source_indices',[])
rows=[r for r in rows if int(r['index']) not in excluded]
for mode in ['extract','reco','pilot']:
 ids=[r['index'] for r in rows if bool(r['input'])==(mode=='extract')]
 if mode=='pilot':ids=ids[:1]
 (spool/f'{mode}.txt').write_text(''.join(i+'\n' for i in ids))
print(archive,archive.stat().st_size)
