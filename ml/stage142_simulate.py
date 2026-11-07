"""Exact installed d32 script with explicit seed/conditions and read-only observer."""
import os
import shutil
import sys
from pathlib import Path

seed=int(os.environ['NU_MU_STAGE142_SEED'])
source=Path(shutil.which('faser_simulate.py')).read_text()
assert source.count('configFlags = initConfigFlags()')==1
source=source.replace('configFlags = initConfigFlags()',f'configFlags = initConfigFlags()\n    configFlags.Random.SeedOffset = {seed}')
source=source.replace('OFLCOND-FASER-04','OFLCOND-FASER-06')
if os.environ.get('NU_MU_STAGE142_OBSERVER','1')=='1':
    needle='sc = cfg.run(maxEvents=args.nevents)';assert source.count(needle)==1
    code='''from AthenaConfiguration.ComponentFactory import CompFactory
    observer=CompFactory.NuMu142.ObserverTool("NuMuObserver", Output="lineage.jsonl")
    cfg.getService("G4UA::FaserUserActionSvc").UserActionTools += [observer]
    sc = cfg.run(maxEvents=args.nevents)'''
    source=source.replace(needle,code)
assert source.count('sys.exit(int(sc.isFailure()))')==1
source=source.replace('sys.exit(int(sc.isFailure()))','import os\n    sys.stdout.flush(); sys.stderr.flush()\n    os._exit(int(sc.isFailure()))')
sys.argv[0]='faser_simulate.py'
exec(compile(source,'stage142-pinned-faser_simulate.py','exec'),{'__name__':'__main__'})
