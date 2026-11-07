"""Unmodified official reconstruction, with event-end CPU instrumentation."""
import json
import os
import shutil
import sys
import time
from pathlib import Path
from AthenaPython import PyAthena
from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator

rdo, count, target = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
cpu, tick = time.process_time(), time.perf_counter()
ends = []
original = ComponentAccumulator.run
conditions = os.environ.get('NU_MU_CONTROL_CONDITIONS', 'OFLCOND-FASER-06')
assert conditions in ['OFLCOND-FASER-04', 'OFLCOND-FASER-06']
official_scope = {'__name__': '__main__'}
configured = {}


class Timing(PyAthena.Alg):
    def execute(self):
        ends.append(time.process_time()-cpu)
        return PyAthena.StatusCode.Success

    def finalize(self):
        target.write_text(json.dumps(dict(event_end_CPU_s=ends, CPU_s=time.process_time()-cpu,
            wall_s=time.perf_counter()-tick, **configured), indent=2)+'\n')
        assert len(ends) == count
        return PyAthena.StatusCode.Success


def run(acc, *args, **kwargs):
    flags = official_scope['configFlags']
    configured.update(conditions=str(flags.IOVDb.GlobalTag), geometry=str(flags.GeoModel.FaserVersion))
    assert configured['conditions'] == conditions and configured['geometry'] == 'FASERNU-04'
    acc.addEventAlgo(Timing('Stage149RecoTiming'))
    return original(acc, *args, **kwargs)


ComponentAccumulator.run = run
source = Path(shutil.which('faser_reco.py')).read_text()
if conditions != 'OFLCOND-FASER-06':
    assert source.count('configFlags.lock()') == 1
    source = source.replace('configFlags.lock()', f'configFlags.IOVDb.GlobalTag = {conditions!r}\nconfigFlags.lock()')
sys.argv = ['faser_reco.py', '--isMC', '--geom', 'TI12MC04', '--nevents', str(count), rdo]
exec(compile(source, 'stage149-official-reco.py', 'exec'), official_scope)
