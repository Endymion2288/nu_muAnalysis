#!/usr/bin/env python3
"""Compare the two requested seed inflations on the frozen rotated runtime."""
import argparse
import gzip
import json
import math
from pathlib import Path
import runpy
import shutil
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('--variance', choices=['large', 'small'], required=True)
    parser.add_argument('--nevents', type=int, default=-1)
    parser.add_argument('--skip', type=int, default=0)
    args = parser.parse_args()
    from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator
    from FaserActsGeometry.RotatedMaterialMap import rotatedMaterialMapPath
    original = ComponentAccumulator.run
    inflation = [100, 100, 100, 10000, 100000] if args.variance == 'large' else [100, 100, 100, 100, 1000]
    target = [81., .0361, .1089, inflation[3] * (2.9e-4)**2, inflation[4] * (1e-4)**2]

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
            assert math.isclose(float(seed.covTheta), 8.41e-4, rel_tol=1e-12)
            assert math.isclose(float(seed.covQOverP), 1e-3, rel_tol=1e-12)
            if args.variance == 'small':
                seed.covTheta = target[3]
                seed.covQOverP = target[4]
            values = {k: float(getattr(seed, k)) for k in
                      ['covLoc0', 'covLoc1', 'covPhi', 'covTheta', 'covQOverP']}
            assert all(math.isclose(x, y, rel_tol=1e-12) for x, y in zip(values.values(), target))
            algorithms[name] = dict(isolated_smoothing=True, seed_covariance=values,
                                   properties={k: repr(v) for k, v in alg._properties.items()})
        assert len(algorithms) == 4
        wave = acc.getEventAlgo('PreshowerWaveformRecAlg').WaveformReconstructionTool
        record = dict(variance=args.variance, initial_variance_inflation=inflation,
            algorithms=algorithms, material_file=str(material), material_bytes=material.stat().st_size,
            exact_strict_map=True, preshower={k: repr(getattr(wave, k)) for k in
                ['FitWindowWidth', 'BaselineSampleHi', 'RemoveOverflow']})
        Path('effective_reco.json').write_text(json.dumps(record, indent=2) + '\n')
        print('EFFECTIVE_COVARIANCE', json.dumps(record), flush=True)
        return original(acc, *positional, **keyword)

    ComponentAccumulator.run = run
    script = shutil.which('faser_reco.py')
    sys.argv = [script, '--isMC', '--geom', 'TI12MC04', '--cond', 'OFLCOND-FASER-06',
                '--nevents', str(args.nevents), '--skip', str(args.skip), args.input]
    runpy.run_path(script, run_name='__main__')


if __name__ == '__main__':
    main()
