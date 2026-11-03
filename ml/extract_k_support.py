"""Stage82 explicit frozen K source, nominal merge, original selection and 62 inputs."""
import argparse
import json
from pathlib import Path
from audited_features import REPO
from extract_alternative_support import extract

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index', type=int, required=True)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--qa', action='store_true')
    a = p.parse_args()
    sources = json.loads((REPO/'workbook/stage82_energy_ml/production_protocol.json').read_text())['sources']
    extract(a.index, a.input, a.output, a.qa, source=sources[a.index])
