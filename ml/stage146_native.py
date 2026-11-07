"""Read the retained HepMC parent graph; no geometry, transport or digitization."""
import gzip
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

OUT = Path('workbook/stage146_energy_ml')
plan = json.loads((OUT/'protocol.json').read_text())
phase = sys.argv[1]
stop = plan['pilot_events'] if phase == 'pilot' else plan['max_events']
tick, cpu = time.perf_counter(), time.process_time()
records = []
event_timing = dict(CPU_s=0., wall_s=0.)
admission = json.loads((OUT/'full_admission.json').read_text()) if phase == 'full' else None
extension_gate = {}
first_event_end_cpu = None


class Snapshot(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        return PyAthena.StatusCode.Success

    def execute(self):
        global first_event_end_cpu
        event_tick, event_cpu = time.perf_counter(), time.process_time()
        store = PyAthena.py_svc('StoreGateSvc')
        info = store.retrieve('EventInfo', 'McEventInfo').event_ID()
        row = dict(entry=len(records), run=int(info.run_number()), event=int(info.event_number()), graphs=[])
        for event in store.retrieve('McEventCollection', 'TruthEvent'):
            particles = list(event.particles())
            ids = [int(p.id()) for p in particles]
            known = set(ids)
            parents, payload = {}, []
            for p in particles:
                ident = int(p.id())
                vertex = p.production_vertex()
                incoming = [int(q.id()) for q in vertex.particles_in()] if vertex else []
                parents[ident] = incoming
                m = p.momentum()
                position = vertex.position() if vertex else None
                payload.append(dict(id=ident, pdg=int(p.pid()), status=int(p.status()), parents=incoming,
                                    p4=[m.px(), m.py(), m.pz(), m.e()],
                                    vertex=[position.x(), position.y(), position.z(), position.t()] if position else None))
            missing = sum(parent not in known for links in parents.values() for parent in links)
            # Kahn reduction detects cycles without Python recursion-depth assumptions.
            pending = {ident: set(links) & known for ident, links in parents.items()}
            children = {ident: [] for ident in known}
            for ident, links in pending.items():
                for parent in links:
                    children[parent].append(ident)
            ready = [ident for ident, links in pending.items() if not links]
            visited = 0
            while ready:
                ident = ready.pop()
                visited += 1
                for child in children[ident]:
                    pending[child].discard(ident)
                    if not pending[child]:
                        ready.append(child)
            roots = [p for p in payload if not p['parents']]
            row['graphs'].append(dict(momentum_unit=str(event.momentum_unit()), length_unit=str(event.length_unit()),
                                      particle_N=len(payload), root_N=len(roots), roots=roots,
                                      duplicate_id_N=len(ids)-len(known), missing_parent_edges=missing,
                                      cycle_or_blocked_N=len(known)-visited,
                                      particle_pdg_counts={str(pdg): sum(p['pdg'] == pdg for p in payload)
                                                           for pdg in sorted(set(p['pdg'] for p in payload))},
                                      all_retained_descendants_mu_root=(bool(roots) and missing == 0 and visited == len(known)
                                                                       and len(ids) == len(known) and all(abs(p['pdg']) == 13 for p in roots))))
            if len(records) == 0:
                row['schema_example_particles'] = payload[:12]
        records.append(row)
        event_timing['CPU_s'] += time.process_time()-event_cpu
        event_timing['wall_s'] += time.perf_counter()-event_tick
        if first_event_end_cpu is None:
            first_event_end_cpu = time.process_time()
        if admission and len(records) == plan['pilot_events']:
            # Include POOL conversion/I/O between algorithm calls, exclude one-time initialization.
            elapsed = time.process_time()-first_event_end_cpu
            projected = time.process_time()+3*elapsed/(len(records)-1)*(stop-len(records))
            extension_gate.update(measured_post_first_event_CPU_s=elapsed, measured_intervals=len(records)-1,
                                  factor=3, projected_total_process_CPU_s=projected,
                                  process_CPU_cap_s=admission['native_process_CPU_cap_s'],
                                  admitted=projected < admission['native_process_CPU_cap_s'])
            if not extension_gate['admitted']:
                return PyAthena.StatusCode.Failure
        if admission and time.process_time() >= admission['native_process_CPU_cap_s']:
            extension_gate['actual_CPU_cap_reached'] = True
            return PyAthena.StatusCode.Failure
        return PyAthena.StatusCode.Success


flags = initConfigFlags()
flags.Input.Files = [plan['HITS']]
flags.Input.isMC = True
flags.IOVDb.DatabaseInstance = 'OFLP200'
flags.Input.ProjectName = 'data21'
flags.GeoModel.FaserVersion = 'FASERNU-04'
flags.IOVDb.GlobalTag = 'OFLCOND-FASER-06'
flags.Concurrency.NumThreads = 0
flags.Exec.MaxEvents = stop
flags.Exec.OutputLevel = 4
flags.lock()
config = MainServicesCfg(flags)
config.merge(PoolReadCfg(flags))
config.addEventAlgo(Snapshot('Stage146RetainedGraph'))
success = config.run(stop).isSuccess()
with gzip.open(OUT/f'{phase}_roots.json.gz', 'wt') as stream:
    json.dump(records, stream, separators=(',', ':'), allow_nan=False)
report = dict(success=success, phase=phase, requested_N=stop, actual_N=len(records),
              first_record=records[0] if records else None,
              graph_algorithm_timing=event_timing,
              extension_gate=extension_gate,
              retained_graph_mu_root_N=sum(bool(r['graphs']) and all(g['all_retained_descendants_mu_root'] for g in r['graphs']) for r in records),
              CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
              ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()), RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              identity='HepMC3 id is graph-local identifier, not assumed ATLAS barcode; joining uses run/event plus float32 root momentum and vertex',
              limit='Retained generator truth graph only; no claim of complete transported-secondary history or radiation-process classification')
(OUT/f'{phase}_native.json').write_text(json.dumps(report, indent=2)+'\n')
print(report, flush=True)
assert success
