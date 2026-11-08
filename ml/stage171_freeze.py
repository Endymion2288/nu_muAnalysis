"""Pre-freeze implementation repair with unchanged RAW physics selection and budget."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage171_energy_ml';OUT.mkdir(exist_ok=True)
p=json.loads((ROOT/'workbook/stage170_energy_ml/protocol.json').read_text())
p.update(stage=171,parent_commit='577d5ef',predecessor='Stage170 original cost gate failed; no 8192 data read.',
    repair='Load each required legacy NPZ member once, outside event loop; gzip transport compression1. No physical selection change.',
    repair_validation='All smoke56 JSON fields and every hardware ADC exactly equal original Stage170; original Stage43 reference exact; measure reference cost separately.',
    stage170_reference='ntuples/energy_ml_stage170/smoke_rows.jsonl.gz')
assert not (OUT/'protocol.json').exists();(OUT/'protocol.json').write_text(json.dumps(p,indent=2)+'\n')
(ROOT/'workbook/stage171_energy_ml/header_sources.json').write_bytes((ROOT/'workbook/stage170_energy_ml/header_sources.json').read_bytes())
