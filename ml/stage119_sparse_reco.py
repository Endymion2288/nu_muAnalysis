"""Run unchanged official reco on an exact, pre-frozen parent entry list."""
import json
import runpy
import shutil
import sys

request=json.load(open(sys.argv[1]));entries=request['entries'];assert entries==sorted(set(entries)) and entries
from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator
original=ComponentAccumulator.run


def selected_run(acc,*args,**kwargs):
    # EventSelector uses 1-based inclusive skip ranges. All retained entries
    # are selected solely by a conservative superset of the original truth
    # fiducial/nu_mu/pz cuts; no reconstructed response or model is consulted.
    excluded=[];left=0
    for entry in entries:
        if left<entry:excluded.append(f'{left+1}-{entry}')
        left=entry+1
    if left<request['parent_N']:excluded.append(f'{left+1}-{request["parent_N"]}')
    acc.getService('EventSelector').SkipEventRanges=','.join(excluded)
    return original(acc,*args,**kwargs)


ComponentAccumulator.run=selected_run
sys.argv=['faser_reco.py','--isMC','--geom','TI12MC04','--nevents',str(len(entries)),request['rdo']]
runpy.run_path(shutil.which('faser_reco.py'),run_name='__main__')
