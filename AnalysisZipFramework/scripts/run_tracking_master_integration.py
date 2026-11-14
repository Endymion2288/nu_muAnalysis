#!/usr/bin/env python3
"""Run the integrated master with its production defaults and record effective settings."""
import argparse
import gzip
import json
from pathlib import Path
import runpy
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('--nevents', type=int, default=-1)
    parser.add_argument('--skip', type=int, default=0)
    args = parser.parse_args()
    from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator
    from FaserActsGeometry.RotatedMaterialMap import rotatedMaterialMapPath
    original = ComponentAccumulator.run

    def run(acc, *positional, **keyword):
        geometry = acc.getService('FaserActsTrackingGeometrySvc')
        material = Path(geometry.MaterialMapInputFile)
        assert geometry.UseMaterialMap and material == Path(rotatedMaterialMapPath())
        assert material.read_bytes() == gzip.decompress(Path('material-strict-reference.json.gz').read_bytes())
        algorithms = {}
        for name, alg in acc._algorithms.items():
            if alg.getType() != 'CKF2':
                continue
            assert alg.IsolateCandidateSmoothing
            seed = alg.TrackSeed
            algorithms[name] = dict(isolated_smoothing=bool(alg.IsolateCandidateSmoothing),
                properties={k: repr(v) for k, v in alg._properties.items()},
                seed_covariance={k: float(getattr(seed, k)) for k in
                    ['covLoc0', 'covLoc1', 'covPhi', 'covTheta', 'covQOverP']})
        assert len(algorithms) == 4, algorithms
        wave = acc.getEventAlgo('PreshowerWaveformRecAlg').WaveformReconstructionTool
        record = dict(algorithms=algorithms, material_file=str(material),
                      material_bytes=material.stat().st_size, exact_strict_map=True,
                      preshower={k: repr(getattr(wave, k)) for k in
                          ['FitWindowWidth', 'BaselineSampleHi', 'RemoveOverflow']})
        Path('effective_reco.json').write_text(json.dumps(record, indent=2) + '\n')
        print('EFFECTIVE_INTEGRATION', json.dumps(record), flush=True)
        return original(acc, *positional, **keyword)

    ComponentAccumulator.run = run
    script = shutil.which('faser_reco.py')
    sys.argv = [script, '--isMC', '--geom', 'TI12MC04', '--cond', 'OFLCOND-FASER-06',
                '--nevents', str(args.nevents), '--skip', str(args.skip), args.input]
    runpy.run_path(script, run_name='__main__')


if __name__ == '__main__':
    main()
