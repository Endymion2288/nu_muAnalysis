#!/usr/bin/env python3
"""One-factor controls on the frozen stage201 runtime; all other steps stay official."""
import argparse
import json
import os
from pathlib import Path
import runpy
import sys

VARIANTS = {
    'native': {},
    'shared': {'smoothing': False},
    'oldprior': {'theta': True, 'qop': True},
    'oldtheta': {'theta': True},
    'oldqop': {'qop': True},
    'material': {'material': True},
    'material_oldprior': {'material': True, 'theta': True, 'qop': True},
    'norefit': {'norefit': True},
    'interfaces': {'interfaces': True},
    'reset': {'reset': True},
    'material_interfaces': {'material': True, 'interfaces': True},
    'material_norefit': {'material': True, 'norefit': True},
}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant', choices=VARIANTS)
    p.add_argument('input')
    p.add_argument('--nevents', type=int, default=1000)
    p.add_argument('--skip', type=int, default=0)
    args = p.parse_args()
    control = VARIANTS[args.variant]
    from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator
    from AthenaConfiguration.ComponentFactory import CompFactory
    original = ComponentAccumulator.run

    def run(acc, *positional, **keyword):
        settings = {}
        for name, alg in acc._algorithms.items():
            if alg.getType() != 'CKF2':
                continue
            alg.IsolateCandidateSmoothing = control.get('smoothing', True)
            alg.BypassRefit = control.get('norefit', False)
            seed = alg.TrackSeed
            if control.get('theta'):
                seed.covTheta = 8.41e-6
            if control.get('qop'):
                seed.covQOverP = 1e-5
            if control.get('reset'):
                seed.ResetEventMaps = True
            if control.get('interfaces'):
                alg.CreateTrkTrackTool = CompFactory.CreateTrkTrackTool(
                    name='CreateTrkTrackTool_' + name, CorrectCovariance=True)
                alg.KalmanFitterTool1.CorrectInterfaces = True
            if os.environ.get('TRACKING_ABLATION_AUDIT') == '1' and name in ['CKF_woIFT', 'CKF_Back_woIFT']:
                alg.AuditFile = name + '.jsonl'
                alg.AuditStates = True
                alg.AuditSelectedStatesOnly = True
            settings[name] = {k: repr(v) for k, v in alg._properties.items()}
            settings[name]['seed_effective'] = {k: repr(getattr(seed, k)) for k in
                ['covLoc0', 'covLoc1', 'covPhi', 'covTheta', 'covQOverP', 'ResetEventMaps']}
        assert len(settings) == 4, settings
        geometry = acc.getService('FaserActsTrackingGeometrySvc')
        if control.get('material'):
            geometry.MaterialMapInputFile = str(Path('material-rotated.json').resolve())
        record = dict(variant=args.variant, control=control, algorithms=settings,
                      geometry={k: repr(v) for k, v in geometry._properties.items()})
        Path('effective_ablation.json').write_text(json.dumps(record, indent=2) + '\n')
        print('EFFECTIVE_ABLATION', json.dumps(record), flush=True)
        return original(acc, *positional, **keyword)

    ComponentAccumulator.run = run
    script = str(Path(__file__).with_name('run_tracking_station.py'))
    sys.argv = [script, 'reco', 'new', args.input, '--nevents', str(args.nevents), '--skip', str(args.skip)]
    runpy.run_path(script, run_name='__main__')


if __name__ == '__main__':
    main()
