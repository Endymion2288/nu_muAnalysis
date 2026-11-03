#!/usr/bin/env python3
"""Bounded native POOL identity and schema QA for the two frozen stage70 files."""
import argparse
import json
import resource
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=int, choices=[0, 1], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True, help='local symlink to the frozen source')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    source = json.loads((repo/'ml/configs/alternative_support_pilot.json').read_text())['sources'][args.index]
    start, cpu = time.perf_counter(), time.process_time()
    from CalypsoConfiguration.AllConfigFlags import initConfigFlags
    from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
    from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
    from AthenaPython import PyAthena
    flags = initConfigFlags()
    assert args.input.resolve() == Path(source['input_rdo']).resolve()
    flags.Input.Files = [str(args.input)]
    flags.Input.isMC = True
    flags.Input.ProjectName = 'data20'
    flags.IOVDb.DatabaseInstance = 'OFLP200'
    flags.GeoModel.FaserVersion = 'FASERNU-04'
    flags.IOVDb.GlobalTag = 'OFLCOND-FASER-06'
    flags.Exec.MaxEvents = 2
    flags.Exec.OutputLevel = 4
    flags.Concurrency.NumThreads = 0
    flags.lock()
    metadata = dict(reader_geometry=str(flags.GeoModel.FaserVersion),
                    reader_conditions=str(flags.IOVDb.GlobalTag),
                    configuration_scope='explicit nominal reader flags; not input production metadata')
    records = []

    class Inspect(PyAthena.Alg):
        def execute(self):
            store = PyAthena.py_svc('StoreGateSvc')
            info = store.retrieve('xAOD::EventInfo', 'EventInfo')
            events = store.retrieve('McEventCollection', 'TruthEvent')
            assert events.size() == 1
            event = events[0]
            particles = list(event.particles())
            # The official ntuple's first truth particle is the GENIE incoming
            # neutrino. Check its identity and momentum against PHYS afterwards;
            # Do not impose an additional no-production-vertex predicate here.
            nu = particles[0]
            assert abs(int(nu.pid())) in [12, 14, 16]
            attrs = list(event.attribute_names())
            records.append(dict(entry=len(records), run=int(info.runNumber()), eventID=int(info.eventNumber()),
                                mcEventNumber=int(info.mcEventNumber()), hepmc_event_number=int(event.event_number()),
                                declared_momentum_enum=int(event.momentum_unit()), declared_length_enum=int(event.length_unit()),
                                incoming_pdg=int(nu.pid()), incoming_raw=[float(getattr(nu.momentum(), k)()) for k in ['px', 'py', 'pz', 'e']],
                                incoming_barcode=str(nu.attribute_as_string('barcode')),
                                attributes={str(k):str(event.attribute_as_string(k)) for k in attrs},
                                particle_N=len(particles)))
            return PyAthena.StatusCode.Success

    acc = MainServicesCfg(flags)
    acc.merge(PoolReadCfg(flags))
    acc.addEventAlgo(Inspect('Stage70IdentityQA'))
    status = acc.run()
    assert status.isSuccess() and len(records) == 2
    metadata['typed_collections'] = list(flags.Input.TypedCollections)
    result = dict(source=source, metadata=metadata, events=records,
                  generator_parent_subfile_seed='not established by two event heads; no independence claim',
                  wall_s=time.perf_counter()-start, cpu_s=time.process_time()-cpu,
                  peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    assert not args.output.exists()
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print('STAGE70_QA', json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
