"""Local stdlib-only immutable transport for the frozen hadronization replay."""
import ast
import json
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage119_energy_ml'
SPOOL=Path.home()/'condor/nu_muAnalysis/stage119'


def main():
    files=json.loads((OUT/'production_package.json').read_text())['files']
    files=[n for n in files if n not in ['ml/stage119_sparse_reco.py','workbook/stage119_energy_ml/production_contract.json']]
    files+=['ml/stage119_sparse_reco.py','workbook/stage119_energy_ml/pythia_production_contract.json']
    mappings={n:('workbook/stage119_energy_ml/production_contract.json' if n.endswith('/pythia_production_contract.json') else n) for n in files}
    archive=ROOT/'software/energy-ml-stage119-pythia-production.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=1) as t:
        for n,arc in mappings.items():
            if n.endswith('.py'):ast.parse((ROOT/n).read_text())
            t.add(ROOT/n,arcname=arc)
    worker=SPOOL/'pythia_production_worker.sh';payload=(ROOT/'AnalysisZipFramework/submission/run_ml_stage119_pythia.sh').read_bytes()
    if worker.exists():assert worker.read_bytes()==payload
    else:worker.write_bytes(payload)
    (SPOOL/'pythia_indices.txt').write_text('\n'.join(map(str,range(18)))+'\n')
    (OUT/'pythia_production_package.json').write_text(json.dumps(dict(mappings=mappings,archive_bytes=archive.stat().st_size),indent=2)+'\n')


if __name__=='__main__':main()
