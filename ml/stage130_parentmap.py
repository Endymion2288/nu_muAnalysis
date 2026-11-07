"""Sparse complete-EVNT identity check after the eventID/entry convention is measured."""
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import ROOT
from AthenaPython import PyAthena
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg

request = json.loads(Path(sys.argv[1]).read_text())
source = request['source']
destination = Path(sys.argv[3])
with np.load(sys.argv[2]) as z:
    entries = np.asarray(z['eventID'], dtype='int64')
    incoming = z['incoming'].astype('float32')
    truth_energy = z['truth_E_GeV']
assert len(set(entries)) == len(entries)
order = np.argsort(entries)
entries, incoming, truth_energy = entries[order], incoming[order], truth_energy[order]
start, end = map(int, source['segment'].split('-'))
assert np.all((entries >= start*1000) & (entries < (end+1)*1000))
cursor, records = 0, []
tick, cpu = time.perf_counter(), time.process_time()


class Snapshot(PyAthena.Alg):
    def execute(self):
        global cursor
        expected_entry = int(entries[cursor])
        events = PyAthena.py_svc('StoreGateSvc').retrieve('McEventCollection', 'BeamTruthEvent')
        assert len(events) == 1
        event = events[0]
        neutrinos = [p for p in event.particles() if abs(p.pid()) == 14 and p.status() == 4]
        assert len(neutrinos) == 1
        p = neutrinos[0].momentum()
        key = np.asarray([neutrinos[0].pid(), p.px(), p.py(), p.pz()], dtype='float32')
        assert np.array_equal(key, incoming[cursor]), (expected_entry, key, incoming[cursor])
        # Actually touch the entire persistent final state, retaining only small
        # identity diagnostics. No FSI genealogy or deployable truth features are inferred.
        particles = []
        for q in event.particles():
            m = q.momentum()
            particles.append((int(q.pid()), int(q.status()), m.px(), m.py(), m.pz(), m.e(), q.generated_mass()))
        vertices = []
        for vertex in event.vertices():
            position = vertex.position()
            vertices.append((position.x(), position.y(), position.z(), position.t(),
                             [int(q.id()) for q in vertex.particles_in()],
                             [int(q.id()) for q in vertex.particles_out()]))
        # HepMC3 enum codes: MEV=1, MM=0; this runtime serializes their
        # Python string form as "1"/"0", rather than the enum names.
        assert int(event.momentum_unit()) == 1 and int(event.length_unit()) == 0
        records.append(dict(eventID=expected_entry, EVNT_entry=expected_entry,
                            particles_N=len(particles), vertices_N=len(vertices),
                            abs_energy_difference_GeV=abs(p.e()/1000 - truth_energy[cursor])))
        cursor += 1
        return PyAthena.StatusCode.Success


if len(entries):
    flags = initConfigFlags()
    flags.Input.Files = [source['EVNT']]
    flags.Input.isMC = True
    flags.Input.ProjectName = 'data21'
    flags.IOVDb.DatabaseInstance = 'OFLP200'
    flags.GeoModel.FaserVersion = 'FASERNU-04'
    flags.IOVDb.GlobalTag = 'OFLCOND-FASER-06'
    flags.Concurrency.NumThreads = 0
    flags.Exec.MaxEvents = len(entries)
    flags.Exec.OutputLevel = 4
    flags.lock()
    accumulator = MainServicesCfg(flags)
    accumulator.merge(PoolReadCfg(flags))
    excluded, left = [], 0
    for entry in entries:
        if left < entry:
            excluded.append(f'{left+1}-{entry}')
        left = int(entry) + 1
    accumulator.getService('EventSelector').SkipEventRanges = ','.join(excluded)
    accumulator.addEventAlgo(Snapshot('Stage130SparseGENIEIdentity'))
    assert accumulator.run(len(entries)).isSuccess()
assert cursor == len(entries)
result = dict(source_index=source['index'], EVNT=source['EVNT'], selected_N=len(entries),
              eventID_entry_incoming_exact_N=cursor, full_final_state_read=True,
              records=records, CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
              ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),
              RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              provenance='path/entry/full-state measured; original GENIE seed/history uncertified')
destination.write_text(json.dumps(result, separators=(',', ':'))+'\n')
print('PARENTMAP', source['index'], cursor, flush=True)
