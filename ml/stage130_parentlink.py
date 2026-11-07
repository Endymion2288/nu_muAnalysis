"""Verify actual complete EVNT parents in the exact source production entry ranges."""
import concurrent.futures
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
OUT = ROOT / 'workbook/stage130_energy_ml'
CACHE = ROOT / 'ntuples/energy_ml_stage130'


def coordinator():
    indices = json.loads((OUT / 'support_pilot_contract.json').read_text())['indices']
    def run(index):
        if (OUT / f'parentlink_{index}.json').exists():
            return dict(index=index, returncode=0, reused_certified_pilot=True)
        with (OUT / f'parentlink_{index}.log').open('w') as stream:
            result = subprocess.run([sys.executable, __file__, str(index)], stdout=stream,
                                    stderr=subprocess.STDOUT)
        return dict(index=index, returncode=result.returncode)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, indices))
    (OUT / 'parentlink_attempts.json').write_text(json.dumps(results, indent=2)+'\n')
    assert all(r['returncode'] == 0 for r in results), results


def worker(index):
    import resource
    import time
    import numpy as np
    import ROOT as R
    from AthenaPython import PyAthena
    from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
    from CalypsoConfiguration.AllConfigFlags import initConfigFlags
    from CalypsoConfiguration.MainServicesConfig import MainServicesCfg

    source = json.loads((OUT / 'source_protocol.json').read_text())['sources'][index]
    proof = next(p for p in json.loads((OUT / 'parent_range_proof.json').read_text())['sources']
                 if p['index'] == index)
    skip, count = proof['skip'], proof['count']
    with np.load(CACHE / f'support_{index}/selected.npz') as z:
        targets = {tuple(k) for k in z['incoming'].astype('float32')}
        selected_N = len(z['incoming'])
        expected_entries = {(int(event), tuple(key)) for event, key in
                            zip(z['eventID'], z['incoming'].astype('float32'))}
    found = {key: [] for key in targets}
    records, scanned = [], 0
    tick, cpu = time.perf_counter(), time.process_time()

    class Snapshot(PyAthena.Alg):
        def execute(self):
            nonlocal scanned
            entry = skip + scanned
            scanned += 1
            events = PyAthena.py_svc('StoreGateSvc').retrieve('McEventCollection', 'BeamTruthEvent')
            for event in events:
                nu = [p for p in event.particles() if abs(p.pid()) == 14 and p.status() == 4]
                if len(nu) != 1:
                    continue
                p = nu[0].momentum()
                key = tuple(np.asarray([nu[0].pid(), p.px(), p.py(), p.pz()], dtype='float32'))
                if key not in targets:
                    continue
                particles, vertices = [], []
                for q in event.particles():
                    momentum = q.momentum()
                    pv, ev = q.production_vertex(), q.end_vertex()
                    particles.append(dict(id=int(q.id()), pdg=int(q.pid()), status=int(q.status()),
                        p=[momentum.px(), momentum.py(), momentum.pz(), momentum.e()],
                        mass=q.generated_mass(), production_vertex=int(pv.id()) if pv else None,
                        end_vertex=int(ev.id()) if ev else None))
                for v in event.vertices():
                    p = v.position()
                    vertices.append(dict(id=int(v.id()), position=[p.x(), p.y(), p.z(), p.t()],
                        incoming=[int(q.id()) for q in v.particles_in()],
                        outgoing=[int(q.id()) for q in v.particles_out()]))
                found[key].append(entry)
                records.append(dict(EVNT=source['EVNT'], entry=entry, incoming=[float(x) for x in key],
                    event_number=event.event_number(), momentum_unit=str(event.momentum_unit()),
                    length_unit=str(event.length_unit()), weights=list(event.weights()),
                    particles=particles, vertices=vertices))
            return PyAthena.StatusCode.Success

    flags = initConfigFlags()
    flags.Input.Files = [source['EVNT']]
    flags.Input.isMC = True
    flags.Input.ProjectName = 'data21'
    flags.IOVDb.DatabaseInstance = 'OFLP200'
    flags.GeoModel.FaserVersion = 'FASERNU-04'
    flags.IOVDb.GlobalTag = 'OFLCOND-FASER-06'
    flags.Concurrency.NumThreads = 0
    flags.Exec.SkipEvents, flags.Exec.MaxEvents = skip, count
    flags.Exec.OutputLevel = 4
    flags.lock()
    accumulator = MainServicesCfg(flags)
    accumulator.merge(PoolReadCfg(flags))
    accumulator.addEventAlgo(Snapshot(f'Stage130ParentLink{index}'))
    assert accumulator.run(count).isSuccess()
    summary = dict(index=index, EVNT=source['EVNT'], skip=skip, requested_N=count, scanned_N=scanned,
        selected_records_N=selected_N, selected_incoming_N=len(targets),
        matched_incoming_N=sum(bool(v) for v in found.values()),
        unmatched_incoming_N=sum(not v for v in found.values()),
        multiple_EVNT_entries_incoming_N=sum(len(v) > 1 for v in found.values()),
        complete_records_N=len(records), CPU_s=time.process_time()-cpu, wall_s=time.perf_counter()-tick,
        selected_eventID_equals_EVNT_entry_matches=sum(
            (record['entry'], tuple(np.asarray(record['incoming'], dtype='float32'))) in expected_entries
            for record in records),
        ROOT_read_bytes=int(R.TFile.GetFileBytesRead()), RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        independence='actual path/entry/full final states; original GENIE seed and unpersisted old exposures remain uncertified',
        FSI='persistent HepMC graph cannot restore flattened GENIE intranuclear process genealogy')
    (CACHE / f'parentlink_{index}.json').write_text(json.dumps(records, separators=(',', ':'))+'\n')
    (OUT / f'parentlink_{index}.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(summary, flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        coordinator()
    else:
        worker(int(sys.argv[1]))
