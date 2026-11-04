"""Stage97 output paths and JSON serialization (CPU-only)."""
import json
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
OUT=REPO/'workbook/stage97_energy_ml'


def save(name,value):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
