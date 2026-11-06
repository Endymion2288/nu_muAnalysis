"""Reuse the validated original selection, feature, identity and payload implementation."""
import json
import subprocess
import sys
from pathlib import Path
root,index=Path(sys.argv[1]),int(sys.argv[2])
request=json.loads(Path('request.json').read_text())
requests=[None]*(index+1);requests[index]=request
out=root/'workbook/stage119_energy_ml';out.mkdir(parents=True,exist_ok=True)
(out/'production_contract.json').write_text(json.dumps(dict(requests=requests)))
subprocess.run([sys.executable,str(root/'ml/stage119_production_extract.py'),str(root),str(index),str(Path('ntuple.root').resolve()),str(Path('result').resolve())],check=True)
