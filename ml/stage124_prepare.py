"""Batch-only exact original-cohort native requests; no new model outcomes."""
import csv,json,time,resource
from pathlib import Path
import numpy as np
import uproot
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage124_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage124'
def main():
 start=time.perf_counter();cpu=time.process_time()
 with np.load(ROOT/'ntuples/energy_ml_stage119/old_input.npz') as z:d={k:z[k] for k in z.files}
 manifests={55:list(csv.DictReader((ROOT/'ml/configs/low_energy_files.tsv').open(),delimiter='\t'))}
 for stage,path in [(70,'ml/configs/alternative_support_pilot.json'),(81,'workbook/stage81_energy_ml/source_plan.json'),(82,'workbook/stage82_energy_ml/production_protocol.json'),(83,'workbook/stage83_energy_ml/protocol.json')]:manifests[stage]=json.loads((ROOT/path).read_text())['sources']
 requests=[];readbytes=0
 for origin,sid in sorted(set(zip(d['origin'].tolist(),d['source'].tolist()))):
  s=manifests[origin][sid];ix=np.flatnonzero((d['origin']==origin)&(d['source']==sid));phys=s.get('input');rdo=s.get('input_rdo') or s.get('rdo')
  if not rdo:
   name=Path(phys).name.replace('-merge-PHYS.root','-RDO.root');tag='master_dev' if 'master_dev' in name else 's0014'
   rdo=f'/eos/experiment/fasernu-data0/faser/sim/mc24/genie/{s["run"]}/rdo/{tag}/{name}'
  if origin==55:
   with uproot.open(phys) as f:
    ids=f['nt']['eventID'].array(library='np');assert len(np.unique(ids))==len(ids);lookup={int(e):j for j,e in enumerate(ids)};entries=[lookup[int(e)] for e in d['eventID'][ix]];parent_N=len(ids);readbytes+=f.file.source.num_requested_bytes
  else:
   with np.load(ROOT/f'ntuples/energy_ml_stage{origin}/support.npz') as z:entries=z['input_entry'][d['origin_row'][ix]].tolist()
   # Known merged parents verified natively by EventSelector/header. Do not infer entries from event number.
   parent_N=10000
  cases=[dict(row=int(j),entry=int(e),event=int(d['eventID'][j]),run=int(d['run'][j]),pz=float(d['pz'][j]),role=int(d['role'][j]),incoming=d['incoming'][j].tolist()) for j,e in zip(ix,entries)]
  cases.sort(key=lambda c:c['entry']);assert len(set(c['entry'] for c in cases))==len(cases)
  rec=rdo.replace('/rdo/','/rec/').replace('-RDO.root','-xAOD.root')
  req=dict(index=len(requests),origin=int(origin),source_index=int(sid),component=s['component'],run=int(s['run']),rdo=rdo,rec=rec,rdo_exists=Path(rdo).is_file(),rec_exists=Path(rec).is_file(),parent_N=parent_N,cases=cases)
  requests.append(req)
 # Reference data copied unchanged, roles/incoming invariants checked without a re-split.
 assert len(d['role'])==89033 and (d['role']==0).sum()==17657
 np.savez_compressed(CACHE/'input.npz',**d)
 contract=json.loads((OUT/'protocol.json').read_text());contract['requests']=requests
 (OUT/'native_contract.json').write_text(json.dumps(contract,separators=(',',':'))+'\n')
 summary=dict(N=len(d['role']),sources=len(requests),active=int((d['role']>0).sum()),rdo_sources=sum(r['rdo_exists'] for r in requests),rec_sources=sum(r['rec_exists'] for r in requests),CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-start,header_read_bytes=readbytes,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
 (OUT/'preparation.json').write_text(json.dumps(summary,indent=2)+'\n')
 (OUT/'source_inventory.json').write_text(json.dumps([{k:v for k,v in r.items() if k!='cases'}|dict(N=len(r['cases'])) for r in requests],indent=2)+'\n')
 print(summary,flush=True)
if __name__=='__main__':main()
