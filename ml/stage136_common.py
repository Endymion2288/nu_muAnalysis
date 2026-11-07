"""Fixed Stage136 inputs and compact tabular output."""
import csv
import json
from pathlib import Path
import numpy as np
from stage131_common import evaluation_masks

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'workbook/stage136_energy_ml'
CACHE = ROOT/'ntuples/energy_ml_stage136'
ART = ROOT/'ml/artifacts/stage136'

def load(path):
    with np.load(ROOT/path, allow_pickle=False) as source:
        return {k:source[k] for k in source.files if k != 'metadata_json'}

def inputs():
    return load('ntuples/energy_ml_stage131/matched_input.npz')

def protocol():
    return json.loads((OUT/'protocol.json').read_text())

def table(name, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, restval='NA',
                                delimiter='\t', lineterminator='\n')
        writer.writeheader()
        writer.writerows({k:('NA' if v is None or v == '' else v)
                          for k,v in row.items()} for row in rows)
