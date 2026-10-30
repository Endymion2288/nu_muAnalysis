#!/usr/bin/env python3
"""Attach official truth matching to every raw candidate, including non-long tracks."""

import argparse
import json
from pathlib import Path
import runpy
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xaod')
    args = parser.parse_args()
    from AthenaPython import PyAthena
    from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator

    class Inspect(PyAthena.Alg):
        def execute(self):
            import ROOT
            ROOT.gInterpreter.AddIncludePath(str(Path(__file__).resolve().parents[1]/'include'))
            assert ROOT.gInterpreter.Declare('#include "TrackingTruthDiagnostic.h"')
            store = PyAthena.py_svc('StoreGateSvc')
            simdata = store.retrieve('TrackerSimDataCollection','SCT_SDO_Map')
            particles = store.retrieve('xAOD::TruthParticleContainer','TruthParticles')
            result = {}
            for mode, key in [('forward', 'CKFTrackCollectionWithoutIFT'),
                              ('backward', 'CKFTrackCollectionBackwardWithoutIFT'),
                              ('merge', 'CKFTrackCollectionMergeWithoutIFT')]:
                rows = []
                for track in store.retrieve('TrackCollection', key):
                    match = list(ROOT.DiagnosticTrackTruth(track,simdata,particles))
                    truth = None
                    if match:
                        truth = dict(barcode=int(match[0]),pdg=int(match[1]),hit_count=int(match[2]),
                                     p_mev=match[3:6],parents=[dict(barcode=int(match[i]),pdg=int(match[i+1]))
                                                            for i in range(6,len(match),2)])
                    first = track.trackParameters().front()
                    position, momentum = first.position(), first.momentum()
                    quality = track.fitQuality()
                    rows.append(dict(first=[float(position.x()),float(position.y()),float(position.z()),
                                            float(momentum.x()),float(momentum.y()),float(momentum.z())],
                                     charge=float(first.charge()), chi2=float(quality.chiSquared()),
                                     ndof=float(quality.doubleNumberDoF()),
                                     measurements=int(track.measurementsOnTrack().size()), truth=truth))
                result[mode] = rows
            Path('raw_truth.json').write_text(json.dumps(result, allow_nan=True, separators=(',', ':')))
            return PyAthena.StatusCode.Success

    original = ComponentAccumulator.run

    def run(accumulator, *positional, **keyword):
        accumulator.addEventAlgo(Inspect('InspectTrackingTruth'))
        return original(accumulator, *positional, **keyword)

    ComponentAccumulator.run = run
    maker = shutil.which('faser_ntuple_maker.py')
    sys.argv = [maker, '--isMC', '--geom', 'TI12MC04', '--CKFTrackType', 'merge',
                '--nevents', '1', '--outfile', 'merge.root', args.xaod]
    runpy.run_path(maker, run_name='__main__')


if __name__ == '__main__':
    main()
