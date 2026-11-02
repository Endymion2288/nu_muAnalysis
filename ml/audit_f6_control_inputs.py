#!/usr/bin/env python3
"""Bounded metadata and <=40-event schema/unit pilot for stage52; no response comparison."""
import csv,json,resource,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import awkward as ak
import uproot

repo=Path(__file__).resolve().parents[1];out=repo/'workbook/stage52_energy_ml';out.mkdir(parents=True,exist_ok=True)
assert not (out/'input_audit.json').exists(),'Do not silently repeat input audit'
rows=list(csv.DictReader((repo/'ml/configs/calonu_muon_files.tsv').open(),delimiter='\t'))
tracks=['p0','pz0','nLayers','nDoF','Chi2','charge','x0','y0','z0','X_atVetoStation2','Y_atVetoStation2','X_atTrig','Y_atTrig','X_atPreshower','Y_atPreshower']
channels=['VetoNu0','VetoNu1','Veto10','Veto20','Veto21','Timing0','Timing1','Timing2','Timing3','Preshower0','Preshower1']
columns=['run','eventID','eventTime','distanceToCollidingBCID','TBP','TAP','inputBits','longTracks','nClusters0','nClusters1','nClusters2','nClusters3','SpacePoints','TrackSegments','GhostBustedTrackSegments']
columns+=['Track_'+k for k in tracks]+[c+'_'+k for c in channels for k in ['charge','raw_charge','raw_peak','status']]
selected={0:10,6:10,12:5,14:5,16:10};assert sum(selected.values())==40
(out/'pilot_protocol.json').write_text(json.dumps(dict(frozen_utc=datetime.now(timezone.utc).isoformat(),starting_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    schema_pilot_entries_per_index=selected,selection='first entries for schema/units only; no data/MC response comparison or residual-driven selection',probe_response_examined=False),indent=2)+'\n')
tick,cp=time.perf_counter(),time.process_time();records=[];pilot=[]
for row in rows:
    start=time.perf_counter();i=int(row['index'])
    with uproot.open(row['input']) as f:
        t=f['nt'];keys=t.keys();missing=sorted(set(columns)-set(keys));present=[c for c in columns if c in keys]
        rec=dict(index=i,sample=row['sample'],run=int(row['run']),group=row['group'],input=row['input'],entries=t.num_entries,file_bytes=Path(row['input']).stat().st_size,
            full_minimal_compressed_bytes=sum(t[c].compressed_bytes for c in present),missing_columns=missing,available_types={c:t[c].typename for c in present})
        if i in selected:
            arr=t.arrays(present,entry_stop=selected[i]);lead=ak.argmax(arr['Track_pz0'],axis=1,keepdims=True)
            lengths=ak.num(arr['Track_pz0'])
            for c in present:
                if c.startswith('Track_'):assert bool(ak.all(ak.num(arr[c])==lengths)),c
            # Do not persist event probe values or compare medians across samples.
            pilot.append(dict(index=i,entries=len(arr),aligned_track_columns=True,counts_integer_types={c:t[c].typename for c in ['nClusters0','SpacePoints','TrackSegments']},
                scalar_probe_fields_present=[c for c in present if c.endswith(('_charge','_peak','_status'))],
                waveform_status_values={c:sorted(set(map(int,ak.to_numpy(arr[c])))) for c in present if c.endswith('_status')},
                leading_index=[int(x) if x is not None else None for x in ak.to_list(ak.flatten(lead))]))
        rec['requested_bytes']=int(f.file.source.num_requested_bytes)
    rec['wall_s']=time.perf_counter()-start;records.append(rec)
summary=dict(files=len(records),full_entries=sum(r['entries'] for r in records),MC_entries=sum(r['entries'] for r in records if r['sample']=='MC'),data_entries=sum(r['entries'] for r in records if r['sample']=='data'),
    estimated_minimal_compressed_bytes=sum(r['full_minimal_compressed_bytes'] for r in records),pilot_events=40,metadata_and_pilot_requested_bytes=sum(r['requested_bytes'] for r in records),
    wall_s=time.perf_counter()-tick,cpu_s=time.process_time()-cp,peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,records=records,pilot=pilot)
(out/'input_audit.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k not in ['records','pilot']}))
print(json.dumps([dict(index=r['index'],sample=r['sample'],entries=r['entries'],compressed_bytes=r['full_minimal_compressed_bytes'],missing=r['missing_columns']) for r in records]))
