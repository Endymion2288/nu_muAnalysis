"""Digitize a frozen truth-only parent superset with original event identities."""
import json
import runpy
import shutil
import sys

from AthenaConfiguration.ComponentAccumulator import ComponentAccumulator

request=json.load(open(sys.argv[1]));entries=request['entries']
assert entries==sorted(set(entries)) and entries
original=ComponentAccumulator.run


def selected_run(acc,*args,**kwargs):
    excluded=[];left=0
    for entry in entries:
        if left<entry:excluded.append(f'{left+1}-{entry}')
        left=entry+1
    if left<request['parent_N']:excluded.append(f'{left+1}-{request["parent_N"]}')
    acc.getService('EventSelector').SkipEventRanges=','.join(excluded)
    return original(acc,*args,**kwargs)


ComponentAccumulator.run=selected_run
sys.argv=['faser_digi.py','--geom','TI12MC04','--nevts',str(len(entries)),request['hits']]
runpy.run_path(shutil.which('faser_digi.py'),run_name='__main__')
