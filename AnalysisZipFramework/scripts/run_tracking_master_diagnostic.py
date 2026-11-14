#!/usr/bin/env python3
"""Explicit stage209 controls; production defaults remain frozen and unchanged."""
import argparse
import gzip
import json
import os
from pathlib import Path
import runpy
import shutil
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input');parser.add_argument('--nevents',type=int,default=-1)
    parser.add_argument('--skip',type=int,default=0)
    args=parser.parse_args()
    from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator
    from AthenaPython import PyAthena
    from FaserActsGeometry.RotatedMaterialMap import rotatedMaterialMapPath
    original=ComponentAccumulator.run
    control=os.environ.get('STAGE209_CONTROL','default')
    allowed=['default','oldqop','oldtheta','oldseed','tightphi','shared',
             'seedp300','seedp1000','seedp3000','seedp10000']
    assert control in allowed,control
    if control.startswith('seedp'):
        os.environ['CALYPSO_DIAG_START_P_GEV']=control[5:]
    class MomentumQuality(PyAthena.Alg):
        def initialize(self):
            import ROOT
            ROOT.gInterpreter.AddIncludePath(str(Path(__file__).resolve().parents[1]/'include'))
            assert ROOT.gInterpreter.Declare('#include "TrackingMomentumQuality.h"')
            self.store=PyAthena.py_svc('StoreGateSvc')
            self.output=gzip.open('momentum_quality.jsonl.gz','wt',compresslevel=1)
            return PyAthena.StatusCode.Success

        def execute(self):
            import ROOT
            event=self.store.retrieve('xAOD::EventInfo','EventInfo')
            keys=['CKFTrackCollectionWithoutIFT','CKFTrackCollectionBackwardWithoutIFT',
                  'CKFTrackCollection','CKFTrackCollectionBackward']
            rows=[[list(ROOT.TrackingMomentumQuality(track))
                   for track in self.store.retrieve('TrackCollection',key)] for key in keys]
            self.output.write(json.dumps([int(event.runNumber()),int(event.eventNumber()),rows],
                separators=(',',':'))+'\n')
            return PyAthena.StatusCode.Success

        def finalize(self):
            self.output.close()
            return PyAthena.StatusCode.Success

    def run(acc,*positional,**keyword):
        geometry=acc.getService('FaserActsTrackingGeometrySvc');material=Path(geometry.MaterialMapInputFile)
        assert material==Path(rotatedMaterialMapPath()) and geometry.UseMaterialMap
        assert material.read_bytes()==gzip.decompress(Path('material-strict-reference.json.gz').read_bytes())
        algorithms={}
        for name,alg in acc._algorithms.items():
            if alg.getType()!='CKF2':continue
            seed=alg.TrackSeed
            if control in ['oldqop','oldseed']:seed.covQOverP=1e-5
            if control in ['oldtheta','oldseed']:seed.covTheta=8.41e-6
            if control=='tightphi':seed.covPhi=8.41e-6
            if control=='shared':alg.IsolateCandidateSmoothing=False
            algorithms[name]=dict(isolated_smoothing=bool(alg.IsolateCandidateSmoothing),
                seed_covariance={k:float(getattr(seed,k)) for k in ['covLoc0','covLoc1','covPhi','covTheta','covQOverP']})
        assert len(algorithms)==4
        Path('effective_reco.json').write_text(json.dumps(dict(control=control,algorithms=algorithms,
            material_file=str(material),exact_strict_map=True),indent=2)+'\n')
        acc.addEventAlgo(MomentumQuality('InspectMomentumCovariance'))
        return original(acc,*positional,**keyword)
    ComponentAccumulator.run=run
    script=shutil.which('faser_reco.py')
    sys.argv=[script,'--isMC','--geom','TI12MC04','--cond','OFLCOND-FASER-06',
        '--nevents',str(args.nevents),'--skip',str(args.skip),args.input]
    runpy.run_path(script,run_name='__main__')


if __name__=='__main__':main()
