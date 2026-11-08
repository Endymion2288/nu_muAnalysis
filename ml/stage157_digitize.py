"""Official prefix digitization with event-specific private waveform RNG seeds."""
import json
import os
import re
import resource
import shutil
import sys
import time
from pathlib import Path

import ROOT
from AthenaPython import PyAthena
from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator
from AthenaConfiguration.ComponentFactory import CompFactory
from PyUtils.MetaReader import read_metadata

begin = int(os.environ.get('NU_MU_CHAIN_BEGIN', '0'))
source_path, count, target = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
tick, cpu = time.perf_counter(), time.process_time()
records = []
original = ComponentAccumulator.run
header = Path(__file__).with_name('stage129_rng.hxx')
conditions = os.environ.get('NU_MU_CONTROL_CONDITIONS', 'OFLCOND-FASER-06')
assert conditions in ['OFLCOND-FASER-04', 'OFLCOND-FASER-06']
official_scope = {'__name__': '__main__'}
configured = {}


def serial(value):
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [serial(v) for v in value]
    return value if value is None or isinstance(value, (str, int, float, bool)) else str(value)


metadata = serial(read_metadata(source_path, mode='full')[source_path])
target.with_name('input_metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
first_end = None


class Seed(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        assert ROOT.gInterpreter.Declare('#define HEPMC3 1\n')
        for lib in ['libWaveRawEvent.so', 'libScintSimEvent.so', 'libxAODFaserWaveform.so']:
            assert ROOT.gSystem.Load(lib) >= 0
        assert ROOT.gInterpreter.Declare(header.read_text())
        return PyAthena.StatusCode.Success

    def execute(self):
        global first_end
        store = PyAthena.py_svc('StoreGateSvc')
        info = store.retrieve('EventInfo', 'McEventInfo').event_ID()
        event, run = int(info.event_number()), int(info.run_number())
        if records:
            records[-1]['after'] = {d: str(ROOT.Stage129PrivateState(d)) for d in records[-1]['seeds']}
        roots = []
        for graph in store.retrieve('McEventCollection', 'TruthEvent'):
            for particle in graph.particles():
                vertex = particle.production_vertex()
                if vertex and len(list(vertex.particles_in())):
                    continue
                p = particle.momentum()
                v = vertex.position() if vertex else None
                roots.append(dict(id=int(particle.id()), pdg=int(particle.pid()),
                                  p4=[p.px(), p.py(), p.pz(), p.e()],
                                  vertex=[v.x(), v.y(), v.z(), v.t()] if v else None))
        seeds, before = {}, {}
        for j, detector in enumerate(['Calo', 'VetoNu', 'Veto', 'Trigger', 'Preshower']):
            value = 720000000+10000*event+1000*j
            assert 0 < value < 2**32
            ROOT.Stage129PrivateSeed(detector, value)
            seeds[detector] = value
            before[detector] = str(ROOT.Stage129PrivateState(detector))
        records.append(dict(entry=begin+len(records), run=run, event=event, roots=roots,
                            seeds=seeds, before=before, execute_entry_CPU_s=time.process_time()-cpu))
        print('SEEDED', len(records), run, event, flush=True)
        return PyAthena.StatusCode.Success

    def finalize(self):
        if records:
            records[-1]['after'] = {d: str(ROOT.Stage129PrivateState(d)) for d in records[-1]['seeds']}
        target.write_text(json.dumps(dict(records=records, CPU_s=time.process_time()-cpu,
            wall_s=time.perf_counter()-tick, ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),
            RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            silicon_SeedOffset=2026110749, conditions=configured['conditions'], geometry=configured['geometry']),
            separators=(',', ':'))+'\n')
        assert len(records) == count
        assert all(any(r['before'][d] != r['after'][d] for d in r['seeds']) for r in records)
        return PyAthena.StatusCode.Success


class EndEvent(PyAthena.Alg):
    def execute(self):
        records[-1]['execute_end_CPU_s'] = time.process_time()-cpu
        return PyAthena.StatusCode.Success


def run(acc, *args, **kwargs):
    flags = official_scope['configFlags']
    configured.update(conditions=str(flags.IOVDb.GlobalTag), geometry=str(flags.GeoModel.FaserVersion))
    assert configured['conditions'] == conditions and configured['geometry'] == 'FASERNU-04'
    acc.getService('EventSelector').SkipEvents = begin
    for detector in ['Calo', 'VetoNu', 'Veto', 'Trigger', 'Preshower']:
        tool = CompFactory.WaveformDigitisationTool('Stage122'+detector)
        acc.getEventAlgo(detector+'WaveformDigiAlg').WaveformDigitisationTool = tool
    acc.addEventAlgo(Seed('Stage149SeededWaveforms'), sequenceName='AthBeginSeq')
    acc.addEventAlgo(EndEvent('Stage149EndEvent'))
    return original(acc, *args, **kwargs)


ComponentAccumulator.run = run
source = Path(shutil.which('faser_digi.py')).read_text()
assert source.count('configFlags = initConfigFlags()') == 1
source = source.replace('configFlags = initConfigFlags()',
                        'configFlags = initConfigFlags()\nconfigFlags.Random.SeedOffset = 2026110749')
source = source.replace('OFLCOND-FASER-04', conditions)
sys.argv = ['faser_digi.py', '--geom', 'TI12MC04', '--nevts', str(count), source_path]
exec(compile(source, 'stage149-official-digi.py', 'exec'), official_scope)
