#!/usr/bin/env python3
"""Read track fit qualities and shared cluster IDs from a diagnostic xAOD."""

import argparse
import runpy
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xaod", help="Use a small xAOD reconstructed with --skip/--nevents")
    parser.add_argument("--geom", default="TI12MC04")
    parser.add_argument("--outfile", default="inspect.root")
    args = parser.parse_args()

    from AthenaPython import PyAthena
    from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator

    class InspectTracks(PyAthena.Alg):
        def execute(self):
            store = PyAthena.py_svc("StoreGateSvc")
            hit_sets = []
            for key in ("CKFTrackCollectionWithoutIFT", "CKFTrackCollectionBackwardWithoutIFT"):
                tracks = store.retrieve("TrackCollection", key)
                for index, track in enumerate(tracks):
                    hits = {int(m.identify().get_compact()) for m in track.measurementsOnTrack()}
                    hit_sets.append((key, index, hits))
                    print("DIAG_HITS", key, index, sorted(hits), flush=True)
                    quality = track.fitQuality()
                    print("DIAG_TRACK", key, index, "chi2", quality.chiSquared(),
                          "dof", quality.doubleNumberDoF(), "measurements",
                          track.measurementsOnTrack().size(), flush=True)
                    for state_index, state in enumerate(track.trackStateOnSurfaces()):
                        quality = state.fitQualityOnSurface()
                        parameters = state.trackParameters()
                        if quality:
                            print("DIAG_STATE", key, index, state_index, "z_mm",
                                  parameters.position().z() if parameters else None,
                                  "chi2", quality.chiSquared(), "dof", quality.numberDoF(),
                                  flush=True)
            for left, first in enumerate(hit_sets):
                for second in hit_sets[left + 1:]:
                    if first[0] != second[0]:
                        print("DIAG_SHARED", first[:2], second[:2], len(first[2] & second[2]),
                              flush=True)
            return PyAthena.StatusCode.Success

    original_run = ComponentAccumulator.run

    def diagnostic_run(accumulator, *positional, **keyword):
        accumulator.addEventAlgo(InspectTracks("InspectTracks"))
        return original_run(accumulator, *positional, **keyword)

    ComponentAccumulator.run = diagnostic_run
    maker = shutil.which("faser_ntuple_maker.py")
    sys.argv = [maker, "--isMC", "--geom", args.geom, "--CKFTrackType", "merge",
                "--outfile", args.outfile, args.xaod]
    runpy.run_path(maker, run_name="__main__")


if __name__ == "__main__":
    main()
