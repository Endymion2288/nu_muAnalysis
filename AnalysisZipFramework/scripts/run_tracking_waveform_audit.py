#!/usr/bin/env python3
"""Inspect actual reconstructed pulse parameters and compare ROOT integration APIs."""
import argparse
import json
from pathlib import Path
import runpy
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input');p.add_argument('--skip',type=int,required=True)
    args = p.parse_args()
    from AthenaPython import PyAthena
    from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator
    import ROOT

    class Inspect(PyAthena.Alg):
        def initialize(self):
            self.store = PyAthena.py_svc('StoreGateSvc')
            assert ROOT.gInterpreter.Declare('''
#include "TF1.h"
#include <vector>
std::vector<double> NuMuCBIntegrals(double peak,double mean,double width,double alpha,double n,double lo,double hi) {
    TF1 f("NuMuCBIntegralCheck", "crystalball",lo,hi);
    f.SetParameters(peak,mean,width,alpha,n);
    double error=0.;double numeric=f.IntegralOneDim(lo,hi,-1,-1,error);
    return {f.Integral(lo,hi),numeric,error};
}
''')
            return PyAthena.StatusCode.Success

        def execute(self):
            event = self.store.retrieve('xAOD::EventInfo','EventInfo')
            rows = []
            for hit in self.store.retrieve('xAOD::WaveformHitContainer','PreshowerWaveformHits'):
                row = {k:float(getattr(hit,k)()) for k in ['peak','mean','width','alpha','nval','integral','raw_integral']}
                row.update(channel=int(hit.channel()),status=int(hit.hit_status()))
                times = list(hit.time_vector())
                if times and row['alpha'] != 0 and row['width'] > 0:
                    row['time_range_ns'] = [float(times[0]),float(times[-1])]
                    row['root_integrals_mV_ns'] = list(ROOT.NuMuCBIntegrals(
                        *[row[k] for k in ['peak','mean','width','alpha','nval']],*row['time_range_ns']))
                rows.append(row)
            Path('waveform_fit_audit.json').write_text(json.dumps(dict(run=int(event.runNumber()),event=int(event.eventNumber()),hits=rows),indent=2)+'\n')
            return PyAthena.StatusCode.Success

    original = ComponentAccumulator.run
    def run(acc,*a,**kw):
        acc.getEventAlgo('PreshowerWaveformRecAlg').WaveformCleanupTool.KeepAll = True
        acc.addEventAlgo(Inspect('InspectWaveformIntegral'))
        return original(acc,*a,**kw)
    ComponentAccumulator.run = run
    script = str(Path(__file__).with_name('run_tracking_ablation.py'))
    sys.argv = [script,'native',args.input,'--nevents','1','--skip',str(args.skip)]
    runpy.run_path(script,run_name='__main__')


if __name__ == '__main__':main()
