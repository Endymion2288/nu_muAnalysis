"""Bounded source endpoints and exact EventInfo identity scan; Condor only."""
import gzip
import json
import resource
import sys
import time
from pathlib import Path

import ROOT
from AthenaPython import PyAthena
from AthenaPoolCnvSvc.PoolReadConfig import PoolReadCfg
from CalypsoConfiguration.AllConfigFlags import initConfigFlags
from CalypsoConfiguration.MainServicesConfig import MainServicesCfg
from PyUtils.MetaReader import read_metadata

OUT=Path('workbook/stage160_energy_ml');CACHE=Path('ntuples/energy_ml_stage160')
phase=sys.argv[1];assert phase in ['headers','pilot','full','audit']
plan=json.loads((OUT/'protocol.json').read_text())
assert json.loads((OUT/'execution_cost_amendment.json').read_text())['frozen_before_any_new_candidate_read']
tick,cpu=time.perf_counter(),time.process_time()


def serial(value):
    if isinstance(value,dict):return {str(k):serial(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,set)):return [serial(v) for v in value]
    return value if value is None or isinstance(value,(str,int,float,bool)) else str(value)


targets=json.loads((OUT/'targets.json').read_text())['records']
target_keys={(r['run'],r['event']) for r in targets}
files=[];metadata=[];cases=[];schemas=[];offset=0
if phase=='headers':requested=[plan['reference_REC']]+plan['candidate_REC']
else:requested=[json.loads((OUT/'locator.json').read_text())['source']['REC']]
for source_index,path in enumerate(requested):
    if not Path(path).is_file():
        metadata.append(dict(source_index=source_index,REC=path,supported=False,reason='Exact frozen path absent; no replacement'))
        assert source_index!=0 or phase!='headers'
        continue
    root=ROOT.TFile.Open(path);assert root and not root.IsZombie()
    tree=root.Get('CollectionTree');assert tree
    total=int(tree.GetEntries());assert total>0
    inventory=[dict(name=b.GetName(),class_name=b.GetClassName()) for b in tree.GetListOfBranches()]
    root.Close()
    if inventory not in schemas:schemas.append(inventory)
    md=serial(read_metadata(path,mode='full')[path])
    metadata.append(dict(source_index=source_index,REC=path,supported=True,N=total,metadata=md,schema_index=schemas.index(inventory)))
    files.append(path)
    if phase=='headers':entries=list(range(4)) if source_index==0 else sorted({0,total-1})
    elif phase=='audit':
        manifest=json.loads((OUT/'matched_manifest.json').read_text())
        entries=sorted({r['native_entry'] for r in manifest['records'] if r['unique_pair']})
        assert entries
    else:entries=[]
    for entry in entries:
        assert 0<=entry<total
        cases.append(dict(source_index=source_index,entry=entry,global_entry=offset+entry))
    offset+=total
if phase in ['headers','audit']:count=len(cases)
else:count=min(1024,offset) if phase=='pilot' else offset
assert count>0 and files
prefix=[];records=[];matches={key:[] for key in target_keys}
event_count=0;previous_start=None;steady_sum=0.;steady_N=0;execute_sum=0.;first_execute=None
event_min=None;event_max=None;runs={}


class Capture(PyAthena.Alg):
    def initialize(self):
        import StoreGateBindings.Bindings
        return PyAthena.StatusCode.Success

    def execute(self):
        global event_count,previous_start,steady_sum,steady_N,execute_sum,first_execute,event_min,event_max
        start=time.process_time()
        if event_count>=2:
            steady_sum+=start-previous_start;steady_N+=1
        previous_start=start
        case=cases[event_count] if cases else dict(source_index=0,entry=event_count)
        store=PyAthena.py_svc('StoreGateSvc');info=store.retrieve('xAOD::EventInfo','EventInfo')
        record=dict(source_index=case['source_index'],entry=case['entry'],run=int(info.runNumber()),
                    event=int(info.eventNumber()),timestamp=int(info.timeStamp()),lumi_block=int(info.lumiBlock()))
        if phase in ['headers','audit']:records.append(record)
        else:
            if event_count<1024:prefix.append(record)
            key=(record['run'],record['event'])
            if key in matches:matches[key].append(record)
        runs[str(record['run'])]=runs.get(str(record['run']),0)+1
        event_min=record['event'] if event_min is None else min(event_min,record['event'])
        event_max=record['event'] if event_max is None else max(event_max,record['event'])
        elapsed=time.process_time()-start;execute_sum+=elapsed
        if first_execute is None:first_execute=elapsed
        event_count+=1
        if event_count in [1,4,64,1024] or event_count%20000==0:print('IDENTITY',phase,event_count,record,flush=True)
        return PyAthena.StatusCode.Success


flags=initConfigFlags();flags.Input.Files=files;flags.Input.isMC=False
flags.Concurrency.NumThreads=0;flags.Exec.MaxEvents=count;flags.Exec.OutputLevel=4;flags.lock()
acc=MainServicesCfg(flags);acc.merge(PoolReadCfg(flags))
if cases:
    left=0;excluded=[]
    for case in cases:
        entry=case['global_entry']
        if left<entry:excluded.append(f'{left+1}-{entry}')
        left=entry+1
    if left<offset:excluded.append(f'{left+1}-{offset}')
    acc.getService('EventSelector').SkipEventRanges=','.join(excluded)
acc.addEventAlgo(Capture('Stage160DataIdentity'))
assert acc.run(maxEvents=count).isSuccess() and event_count==count
payload=dict(records=records,prefix=prefix,target_matches=[dict(run=k[0],event=k[1],native_matches=v) for k,v in matches.items()])
CACHE.mkdir(parents=True,exist_ok=True)
with gzip.open(CACHE/f'{phase}.json.gz','wt') as stream:json.dump(payload,stream,separators=(',',':'))
report=dict(passed=True,phase=phase,N=event_count,source_N=offset,metadata=metadata,schemas=schemas,
    native_runs=runs,event_min=event_min,event_max=event_max,first_execute_CPU_s=first_execute,execute_CPU_s=execute_sum,
    steady_complete_interval_N=steady_N,steady_complete_interval_CPU_s=steady_sum,
    steady_complete_interval_mean_CPU_s=steady_sum/steady_N if steady_N else None,
    CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,ROOT_read_bytes=int(ROOT.TFile.GetFileBytesRead()),
    RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    scope='EventInfo only; no detector geometry, state, waveform payload, energy fit or G4')
(OUT/f'{phase}_summary.json').write_text(json.dumps(report,indent=2)+'\n')
print({k:v for k,v in report.items() if k not in ['metadata','schemas']},flush=True)
