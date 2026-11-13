#!/usr/bin/env python3
"""Run frozen Calypso with explicit smoothing and compact raw-track diagnostics."""
import argparse
import gzip
import json
from pathlib import Path
import runpy
import shutil
import sys

FIELDS = ('x_mm y_mm z_mm px_mev py_mev pz_mev charge chi2 ndof measurements '
          'layers station_mask long barcode pdg truth_hits truth_px_mev '
          'truth_py_mev truth_pz_mev neutrino_parent').split()
KEYS = ('CKFTrackCollectionWithoutIFT', 'CKFTrackCollectionBackwardWithoutIFT',
        'CKFTrackCollectionMergeWithoutIFT')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['reco', 'merge'])
    parser.add_argument('input')
    parser.add_argument('--nevents', type=int, default=-1)
    parser.add_argument('--skip', type=int, default=0)
    args = parser.parse_args()
    from AthenaPython import PyAthena
    from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator
    import ROOT

    class Inspect(PyAthena.Alg):
        def initialize(self):
            self.output = gzip.open('raw_tracks.jsonl.gz', 'wt', compresslevel=3)
            self.events = 0
            self.store = PyAthena.py_svc('StoreGateSvc')
            return PyAthena.StatusCode.Success

        def execute(self):
            if self.events == 0:
                ROOT.gInterpreter.AddIncludePath(str(Path(__file__).resolve().parents[1] / 'include'))
                assert ROOT.gInterpreter.Declare('#include "TrackingDuplicateDiagnostic.h"')
                detector = PyAthena.py_svc('StoreGateSvc/DetectorStore')
                self.helper = detector.retrieve('FaserSCT_ID', 'FaserSCT_ID')
            self.events += 1
            tracks = [self.store.retrieve('TrackCollection', key) for key in KEYS]
            if not any(len(collection) for collection in tracks):
                return PyAthena.StatusCode.Success
            event = self.store.retrieve('xAOD::EventInfo', 'EventInfo')
            sim = self.store.retrieve('TrackerSimDataCollection', 'SCT_SDO_Map')
            particles = self.store.retrieve('xAOD::TruthParticleContainer', 'TruthParticles')
            rows = []
            for collection in tracks:
                rows.append([dict(values=list(ROOT.DuplicateTrackSummary(t, self.helper, sim, particles)),
                                  hits=list(ROOT.DuplicateTrackHits(t, self.helper, False)),
                                  merge_hits=list(ROOT.DuplicateTrackHits(t, self.helper, True)))
                             for t in collection])
            self.output.write(json.dumps([int(event.runNumber()), int(event.eventNumber()), rows],
                                         separators=(',', ':'), allow_nan=True) + '\n')
            return PyAthena.StatusCode.Success

        def finalize(self):
            self.output.close()
            Path('raw_metadata.json').write_text(json.dumps(dict(events=self.events, fields=FIELDS)))
            return PyAthena.StatusCode.Success

    original = ComponentAccumulator.run

    def run(acc, *positional, **keyword):
        if args.operation == 'reco':
            settings = {}
            for name, alg in acc._algorithms.items():
                if alg.getType() != 'CKF2':
                    continue
                alg.IsolateCandidateSmoothing = True
                properties = ('IsolateCandidateSmoothing', 'MaterialEnergyLoss', 'MaterialScattering',
                              'BypassRefit', 'FixedTruthHits', 'ElectronHypothesis',
                              'MaxStepSize', 'SeedOverrideFile', 'AuditFile', 'AuditClosure')
                settings[name] = {p: getattr(alg, p) for p in properties}
            if len(settings) != 4:
                raise RuntimeError(f'expected four default CKF2 collections: {settings}')
            Path('effective_reco.json').write_text(json.dumps(settings, indent=2))
            print('EFFECTIVE_RECO', json.dumps(settings), flush=True)
        else:
            acc.addEventAlgo(Inspect('InspectDuplicateTracks'))
        return original(acc, *positional, **keyword)

    ComponentAccumulator.run = run
    if args.operation == 'reco':
        # This version's --cond log statement uses args.config by mistake.
        # Supply its logging alias while leaving the requested conditions intact.
        original_parse = argparse.ArgumentParser.parse_args
        def parse_with_condition_alias(parser, *positional, **keyword):
            namespace = original_parse(parser, *positional, **keyword)
            namespace.config = namespace.cond
            return namespace
        argparse.ArgumentParser.parse_args = parse_with_condition_alias
    script = shutil.which('faser_reco.py' if args.operation == 'reco' else 'faser_ntuple_maker.py')
    sys.argv = [script, '--isMC', '--geom', 'TI12MC04', '--cond', 'OFLCOND-FASER-06',
                '--nevents', str(args.nevents)]
    if args.operation == 'reco':
        sys.argv += ['--skip', str(args.skip)]
    else:
        sys.argv += ['--CKFTrackType', 'merge', '--outfile', 'merge.root']
    sys.argv += [args.input]
    runpy.run_path(script, run_name='__main__')


if __name__ == '__main__':
    main()
