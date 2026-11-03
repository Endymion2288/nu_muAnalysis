#!/usr/bin/env python3
"""Publish the immutable stage70 extractor, existing binary and worker."""
import json
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
protocol = json.loads((REPO/'workbook/stage70_energy_ml/protocol.json').read_text())
assert protocol['full_files'] and protocol['resources']['condor_jobs'] == 2
archive = REPO/'software/energy-ml-alternative-support-stage70.tar.gz'
assert not archive.exists()
paths = ['setup_env.sh', 'build/analysis', 'AnalysisZipFramework/config', 'AnalysisZipFramework/include',
         'AnalysisZipFramework/submission/validate_merge_ntuple.py',
         'ml/extract_alternative_support.py', 'ml/audited_features.py', 'ml/frozen_evaluation.py',
         'ml/track_response.py', 'ml/train_bdt.py', 'ml/configs/alternative_support_pilot.json',
         'ml/configs/audited_features.json', 'ml/configs/baseline.yaml', 'ml/configs/track_response.yaml',
         'workbook/stage70_energy_ml/protocol.json']
paths += [str(p.relative_to(REPO)) for p in (REPO/'build').glob('*.so')]
with tarfile.open(archive, 'w:gz', compresslevel=1) as tar:
    for path in paths:
        tar.add(REPO/path, arcname=path)
spool = Path('/afs/cern.ch/user/x/xcheng/nu_mu_stage70')
(spool/'logs').mkdir(parents=True, exist_ok=True)
worker = (REPO/'AnalysisZipFramework/submission/run_ml_alternative_support.sh').read_bytes()
assert not (spool/'worker_v1.sh').exists()
(spool/'worker_v1.sh').write_bytes(worker)
(REPO/'ntuples/energy_ml_stage70').mkdir(exist_ok=True)
result = dict(payload_bytes=archive.stat().st_size,
              official_runtime_archive_bytes=(REPO/'software/calypso-master-d32b0ff3-el9-gcc13.tar.gz').stat().st_size,
              paths=paths, source_event_inputs_in_payload=0, compiled=False,
              build_info=Path('/tmp/nu_mu_stage17_runtime/NU_MU_BUILD_INFO.txt').read_text())
(REPO/'workbook/stage70_energy_ml/package.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
