#!/usr/bin/env python3
"""Run the frozen old/new reconstruction or inspect local fitted states during the merge maker."""
import argparse
import gzip
import json
from pathlib import Path
import runpy
import shutil
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['reco','merge'])
    p.add_argument('version',choices=['old','new'])
    p.add_argument('input')
    p.add_argument('--skip',type=int,default=0)
    p.add_argument('--nevents',type=int,default=-1)
    args=p.parse_args()
    if args.operation=='reco' and args.version=='new':
        sys.argv=[str(Path(__file__).with_name('run_tracking_georotation.py')),'reco',args.input,
                  '--skip',str(args.skip),'--nevents',str(args.nevents)]
        runpy.run_path(sys.argv[0],run_name='__main__');return
    from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator
    from AthenaPython import PyAthena
    from run_tracking_georotation import KEYS

    class Inspect(PyAthena.Alg):
        def initialize(self):
            import ROOT
            ROOT.gInterpreter.AddIncludePath(str(Path(__file__).resolve().parents[1]/'include'))
            assert ROOT.gInterpreter.Declare('#include "TrackingStationDiagnostic.h"')
            self.store=PyAthena.py_svc('StoreGateSvc')
            self.helper=PyAthena.py_svc('StoreGateSvc/DetectorStore').retrieve('FaserSCT_ID','FaserSCT_ID')
            self.output=gzip.open('station_states.jsonl.gz','wt',compresslevel=1)
            return PyAthena.StatusCode.Success

        def execute(self):
            import ROOT
            event=self.store.retrieve('xAOD::EventInfo','EventInfo')
            sim=self.store.retrieve('TrackerSimDataCollection','SCT_SDO_Map')
            particles=self.store.retrieve('xAOD::TruthParticleContainer','TruthParticles')
            collections=[]
            for key in KEYS:
                rows=[]
                for track in self.store.retrieve('TrackCollection',key):
                    summary=list(ROOT.StationTrackSummary(track,self.helper,sim,particles,args.version=='new'))
                    states=list(ROOT.StationTrackStates(track,args.version=='new')) if summary[12] else []
                    rows.append([summary,states])
                collections.append(rows)
            self.output.write(json.dumps([int(event.runNumber()),int(event.eventNumber()),collections],
                                         separators=(',',':'),allow_nan=True)+'\n')
            return PyAthena.StatusCode.Success

        def finalize(self):
            self.output.close()
            return PyAthena.StatusCode.Success

    original=ComponentAccumulator.run
    def run(acc,*positional,**keyword):
        if args.operation=='merge':acc.addEventAlgo(Inspect('InspectLocalStationMomentum'))
        else:
            settings={}
            for name,alg in acc._algorithms.items():
                if alg.getType()=='CKF2':
                    settings[name]={k:repr(v) for k,v in alg._properties.items()}
            Path('effective_reco.json').write_text(json.dumps(settings,indent=2))
        return original(acc,*positional,**keyword)
    ComponentAccumulator.run=run
    script=shutil.which('faser_reco.py' if args.operation=='reco' else 'faser_ntuple_maker.py')
    sys.argv=[script,'--isMC','--geom','TI12MC04','--nevents',str(args.nevents)]
    if args.operation=='reco':sys.argv+=['--skip',str(args.skip)]
    else:sys.argv+=['--CKFTrackType','merge','--outfile','merge.root']
    # Official old default is OFLCOND-FASER-06; new maker default is overridden.
    if args.version=='new':sys.argv+=['--cond','OFLCOND-FASER-06']
    sys.argv+=[args.input]
    runpy.run_path(script,run_name='__main__')


if __name__=='__main__':main()
