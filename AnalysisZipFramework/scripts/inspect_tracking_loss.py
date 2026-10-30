#!/usr/bin/env python3
"""Make a merge ntuple and record measurement identities without changing reconstruction."""

import argparse
import json
from pathlib import Path
import runpy
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xaod')
    parser.add_argument('--output', default='measurements.json')
    args = parser.parse_args()
    from AthenaPython import PyAthena
    from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator

    class Inspect(PyAthena.Alg):
        def execute(self):
            store = PyAthena.py_svc('StoreGateSvc')
            helper = PyAthena.py_svc('DetectorStore').retrieve('FaserSCT_ID', 'FaserSCT_ID')
            result = {}
            for mode, key in [('forward', 'CKFTrackCollectionWithoutIFT'),
                              ('backward', 'CKFTrackCollectionBackwardWithoutIFT'),
                              ('merge', 'CKFTrackCollectionMergeWithoutIFT')]:
                rows = []
                for track in store.retrieve('TrackCollection', key):
                    hits = []
                    for measurement in track.measurementsOnTrack():
                        identifier = measurement.identify()
                        hits.append([int(getattr(helper, field)(identifier))
                                     for field in ('station', 'layer', 'side', 'strip')])
                    states = []
                    for state in track.trackStateOnSurfaces():
                        parameters = state.trackParameters()
                        if parameters:
                            position, momentum = parameters.position(), parameters.momentum()
                            states.append([float(position.x()), float(position.y()), float(position.z()),
                                           float(momentum.x()), float(momentum.y()), float(momentum.z())])
                    quality = track.fitQuality()
                    rows.append(dict(hits=hits, states=states, chi2=float(quality.chiSquared()),
                                     ndof=float(quality.doubleNumberDoF())))
                result[mode] = rows
            Path(args.output).write_text(json.dumps(result, allow_nan=True))
            return PyAthena.StatusCode.Success

    original = ComponentAccumulator.run

    def run(accumulator, *positional, **keyword):
        accumulator.addEventAlgo(Inspect('InspectTrackingLoss'))
        return original(accumulator, *positional, **keyword)

    ComponentAccumulator.run = run
    maker = shutil.which('faser_ntuple_maker.py')
    sys.argv = [maker, '--isMC', '--geom', 'TI12MC04', '--CKFTrackType', 'merge',
                '--nevents', '1', '--outfile', 'merge.root', args.xaod]
    runpy.run_path(maker, run_name='__main__')


if __name__ == '__main__':
    main()
