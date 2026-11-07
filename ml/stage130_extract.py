"""Reuse exact Stage119 typed62, native cuts and per-run calibration QA."""
import json
import subprocess
import sys
from pathlib import Path

root, index = Path(sys.argv[1]), int(sys.argv[2])
request = json.loads(Path('request.json').read_text())
requests = [None] * (index + 1)
requests[index] = request
out = root / 'workbook/stage119_energy_ml'
out.mkdir(parents=True, exist_ok=True)
(out / 'production_contract.json').write_text(json.dumps(dict(requests=requests)))
subprocess.run([sys.executable, str(root / 'ml/stage119_production_extract.py'), str(root), str(index),
                str(Path('ntuple.root').resolve()), str(Path('result').resolve())], check=True)

import numpy as np
from latent_transfer_diagnostics import check_x

with np.load('result/selected.npz') as z:
    check_x(z['x'])
    e, pz, y = z['truth_E_GeV'], z['reco_pz_GeV'], z['y_lepton']
    layers = dict(all=np.ones(len(e), bool), E50_100=(e >= 50) & (e < 100),
                  E100_200=(e >= 100) & (e < 200), lowpz_highE=(pz < 100) & (e >= 200),
                  high_y=np.isfinite(y) & (y >= .8) & (y < 1), highE=e >= 1000)
    qa = dict(index=index, selected_N=len(e), parent_N=request['parent_N'],
              truth_superset_N=len(request['entries']),
              counts={k: int(v.sum()) for k, v in layers.items()},
              unique_incoming_N=len(np.unique(z['incoming'], axis=0)),
              inherited_role=request['source']['inherited_role'],
              schema_and_typed_domains_passed=True, model_fits=0, predictions=0,
              feature_metadata=json.loads(str(z['metadata_json'])))
Path('result/source_qa.json').write_text(json.dumps(qa, indent=2) + '\n')
