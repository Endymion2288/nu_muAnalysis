"""Read only actual EventInfo and file metadata from the frozen real-data prefix."""
import json
import resource
import sys
import time
from pathlib import Path

import ROOT
from AthenaPython import PyAthena
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from PyUtils.MetaReader import read_metadata

OUT = Path('workbook/stage159_energy_ml')
plan = json.loads((OUT / 'protocol.json').read_text())
count = int(sys.argv[1])
assert count in [4, 64]
tick, cpu = time.perf_counter(), time.process_time()
source = plan['sources']['REC']


def serial(value):
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [serial(v) for v in value]
    return value if value is None or isinstance(value, (str, int, float, bool)) else str(value)


metadata = serial(read_metadata(source, mode='full')[source])
root = ROOT.TFile.Open(source)
assert root and not root.IsZombie()
tree = root.Get('CollectionTree')
assert tree and tree.GetEntries() >= 64
schema = [dict(name=b.GetName(), class_name=b.GetClassName()) for b in tree.GetListOfBranches()]
entries = int(tree.GetEntries())
root.Close()
records = []


class Capture(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        return PyAthena.StatusCode.Success

    def execute(self):
        store = PyAthena.py_svc('StoreGateSvc')
        info = store.retrieve('xAOD::EventInfo', 'EventInfo')
        records.append(dict(entry=len(records), run=int(info.runNumber()), event=int(info.eventNumber()),
                            lumi_block=int(info.lumiBlock()), timestamp=int(info.timeStamp())))
        return PyAthena.StatusCode.Success


flags = initConfigFlags()
flags.Input.Files = [source]
flags.Input.isMC = False
flags.Concurrency.NumThreads = 0
flags.Exec.MaxEvents = count
flags.Exec.OutputLevel = 4
# No geometry, conditions or detector algorithms: defaults are not source evidence.
flags.lock()
acc = MainServicesCfg(flags)
acc.merge(PoolReadCfg(flags))
acc.addEventAlgo(Capture('Stage159DataIdentity'))
assert acc.run(maxEvents=count).isSuccess()
assert len(records) == count
report = dict(source=source, native_entries=entries, records=records, metadata=metadata, schema=schema,
    requested_prefix=count, CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
    ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()), RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    scope='File metadata and actual EventInfo only; no tracker/waveform payload, no geometry or producer equivalence certification')
(OUT / f'native_{count}.json').write_text(json.dumps(report, indent=2)+'\n')
print({k:v for k,v in report.items() if k not in ['records','metadata','schema']}, flush=True)
