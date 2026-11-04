"""Bounded native provenance/schema audit on batch, no guessed event matching."""
import json,csv,time,resource
from pathlib import Path
import uproot
R=Path(__file__).resolve().parents[1];O=R/'workbook/stage99_energy_ml';O.mkdir(exist_ok=True,parents=True)
t=time.perf_counter();cpu=time.process_time();co=json.loads((R/'ntuples/energy_ml_stage95/cohort.json').read_text());manifest=[x.split('\t') for x in (R/'AnalysisZipFramework/submission/merge_manifest.tsv').read_text().splitlines()];lookup={x[4]:x for x in manifest};records=[]
for s in co['sources']:
 row=dict(source=s['source'],N=sum(x['source']==s['source'] for x in co['records']),phys=s['input'],production='scratch_reconstruction_then_PHYS_only',native_status='not_persisted',native=None)
 if s['input'] in lookup:
  m=lookup[s['input']];row['original_RDO']=m[3];base=Path(m[3]).parents[2];recdir=base/'rec'/m[1];row['known_rec_directory']=str(recdir)
  # Exact corresponding basename in the known production directory, metadata only.
  rec=recdir/Path(m[3]).name.replace('-RDO.root','-xAOD.root');row['corresponding_REC_exists']=rec.is_file();row['candidate_REC']=str(rec)
  if rec.is_file():
   row['native_status']='candidate_different_production_unverified';row['native']=str(rec)
   with uproot.open(rec) as f:row['native_schema']=f['CollectionTree'].typenames();row['native_metadata_requested_bytes']=f.file.source.num_requested_bytes
 if s['input'] and Path(s['input']).is_file():
  with uproot.open(s['input']) as f:
   tree=f['nt'];row['PHYS_schema']={k:v for k,v in tree.typenames().items() if any(x in k.lower() for x in ['space','cluster','sct','sp_','cov','track_','segment'])};row['PHYS_metadata_requested_bytes']=int(f.file.source.num_requested_bytes)
 records.append(row)
qa=[{k:x[k] for k in ['row','key_id','source','role','pz_GeV','status_other']} for x in co['records'] if x['qa']][:40]
r=dict(sources=records,QA_identities=qa,N=co['N'],unique_incoming=co['unique_incoming'],CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-t,peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,no_native_event_reads=True)
(O/'native_entry_QA.json').write_text(json.dumps(r,indent=2));print(json.dumps({k:v for k,v in r.items() if k!='sources'}),flush=True)
