"""Condor-only original-source scalar reads; no replacement production or fit."""
import csv,json,time,resource,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import awkward as ak
import uproot
from audited_features import configuration,SCINTILLATORS,WAVE_INVALID,FIT_INVALID
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage163_energy_ml';CACHE=ROOT/'ntuples/energy_ml_stage163'
PILOT=[0,254,255,257,260];BATCHES=8
FIELDS=['run','eventID','Track_pz0']+[s+'_raw_charge' for s in SCINTILLATORS]+[f'Calo{i}_{k}' for i in range(4) for k in ['raw_charge','status','baseline_rms','E_EM']]

def load():
 with np.load(ROOT/'ntuples/energy_ml_stage119/old_input.npz') as z:return {k:z[k] for k in z.files if k!='metadata_json'}
def write(name,data):(OUT/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
def table(name,rows):
 if not rows:return
 with (OUT/name).open('w') as stream:
  w=csv.DictWriter(stream,fieldnames=list(dict.fromkeys(k for r in rows for k in r)),delimiter='\t',lineterminator='\n',quoting=csv.QUOTE_NONNUMERIC);w.writeheader();w.writerows(rows)
def freeze(d):
 manifests={55:list(csv.DictReader((ROOT/'ml/configs/low_energy_files.tsv').open(),delimiter='\t'))}
 for stage,path in [(70,'ml/configs/alternative_support_pilot.json'),(81,'workbook/stage81_energy_ml/source_plan.json'),(82,'workbook/stage82_energy_ml/production_protocol.json'),(83,'workbook/stage83_energy_ml/protocol.json')]:manifests[stage]=json.loads((ROOT/path).read_text())['sources']
 requests=json.loads((ROOT/'workbook/stage124_energy_ml/native_contract.json').read_text())['requests'];records=[]
 for r in requests:
  source=manifests[r['origin']][r['source_index']];path=source.get('input')
  # Stage82 'input' is the rejected backward candidate. Its selected support
  # came from a separately produced scratch merge PHYS, which was not retained.
  if r['origin']==82:path=None
  # Sources made in transient Stage70/82 ntuple.root were not retained. No alternate REC/PHYS inference.
  exists=bool(path and Path(path).is_file());active=[c for c in r['cases'] if c['role']>0]
  for c in active:
   j=c['row'];assert (int(d['origin'][j]),int(d['source'][j]),int(d['run'][j]),int(d['eventID'][j]),int(d['role'][j]))==(r['origin'],r['source_index'],c['run'],c['event'],c['role'])
  records.append(dict(index=r['index'],origin=r['origin'],source_index=r['source_index'],component=r['component'],run=r['run'],
   path=path,exists=exists,file_bytes=Path(path).stat().st_size if exists else None,active_N=len(active),
   field_mapping='Exact original isMC Calo0-3; never alias data CaloLo/CaloHi',
   producer='d32-declared' if exists and ('master_d32b0ff3' in path or source.get('PHYS_kind','').startswith('d32b0ff3')) else 'historical definition not byte-certified' if exists else 'original temporary PHYS not retained/no exact path',
   waveform_integral_definition='signed entire saved window by d32 dd56a65e source' if exists and ('master_d32b0ff3' in path or source.get('PHYS_kind','').startswith('d32b0ff3')) else 'unknown as-produced, no signed/positive-part equivalence assumed',cases=active))
 assert sum(r['active_N'] for r in records)==71376
 write('source_manifest.json',dict(records=records,fields=FIELDS,source_freeze_before_ROOT=True))
 table('source_inventory.tsv',[{k:v for k,v in r.items() if k!='cases'} for r in records])
 return records

def read_source(r,d,phase):
 cpu,tick=time.thread_time(),time.perf_counter();cases=r['cases']
 if phase=='pilot':cases=[c for c in cases if c['role']==1][:40]
 elif phase=='repeat':cases=[c for c in cases if c['role']==1][:4]
 n=len(cases);row=np.asarray([c['row'] for c in cases],int)
 result=dict(row=row,raw=np.full((n,4),np.nan),status=np.full((n,4),np.nan),rms=np.full((n,4),np.nan),fit_E=np.full((n,4),np.nan))
 base=dict(index=r['index'],origin=r['origin'],phase=phase,N=n,path=r['path'],file_exists=r['exists'],identity_exact_N=0,scint_raw_exact_N=0,pz0_exact_N=0,ROOT_read_bytes=0,payload_CPU_s=0.,startup_CPU_s=0.,read_entries=0,branch_compressed_bytes=0,source_entries=0)
 if not n or not r['exists']:
  base.update(reason='no original train parents' if not n else 'original PHYS unavailable; new fields unknown, parent retained',CPU_s=time.thread_time()-cpu,wall_s=time.perf_counter()-tick)
  return result,base
 entries=np.asarray([c['entry'] for c in cases]);start=int(entries.min());stop=int(entries.max())+1
 with uproot.open(r['path'],array_cache=None) as file:
  tree=file['nt'];schema=set(tree.keys());missing=[b for b in FIELDS if b not in schema]
  base.update(source_entries=int(tree.num_entries),missing_fields=missing,branch_compressed_bytes=sum(tree[b].compressed_bytes for b in FIELDS if b in schema))
  if missing:
   base.update(reason='exact scalar mapping unsupported; no alias guess',ROOT_read_bytes=int(file.file.source.num_requested_bytes),CPU_s=time.thread_time()-cpu,wall_s=time.perf_counter()-tick)
   return result,base
  base['startup_CPU_s']=time.thread_time()-cpu;readcpu=time.thread_time()
  # Bounded pilot range; whole original source range for full active cases, scalar branches only.
  values=tree.arrays(FIELDS,entry_start=start,entry_stop=stop,library='ak')
  base['payload_CPU_s']=time.thread_time()-readcpu;selection=entries-start
  ids=ak.to_numpy(values['eventID']);runs=ak.to_numpy(values['run'])
  assert len(np.unique(ids))==len(ids)
  np.testing.assert_array_equal(ids[selection],d['eventID'][row]);np.testing.assert_array_equal(runs[selection],d['run'][row])
  base['identity_exact_N']=n
  cfg=configuration();x=d['x'][row]
  for detector in SCINTILLATORS:
   # Original typed raw may be missing due to WAVE_INVALID; never compare it to a fitted fallback.
   target=x[:,cfg['features'].index(detector+'_raw_charge')];v=ak.to_numpy(values[detector+'_raw_charge'])[selection].astype('float32')
   np.testing.assert_array_equal(v[np.isfinite(target)],target[np.isfinite(target)],
    err_msg=f"original source gate: request={r['index']} origin={r['origin']} detector={detector} path={r['path']}")
   base['scint_raw_exact_N']+=int(np.isfinite(target).sum())
  pz=[ak.to_list(values['Track_pz0'][int(k)]) for k in selection]
  lead=np.asarray([max(v)/1000 if v else np.nan for v in pz]).astype('float32')
  np.testing.assert_array_equal(lead,d['pz'][row].astype('float32'));base['pz0_exact_N']=n
  for j in range(4):
   for key,suffix in [('raw','raw_charge'),('status','status'),('rms','baseline_rms'),('fit_E','E_EM')]:
    result[key][:,j]=ak.to_numpy(values[f'Calo{j}_{suffix}'])[selection]
  base.update(ROOT_read_bytes=int(file.file.source.num_requested_bytes),read_entries=stop-start,range_start=start,range_stop=stop,reason='actual original scalar measurement')
 base.update(CPU_s=time.thread_time()-cpu,wall_s=time.perf_counter()-tick)
 return result,base

def represent(raw,status,rms):
 known=np.isfinite(status)&(status>=0)&(status==np.floor(status))&(status<4294967295)
 code=np.where(known,status,0).astype('int64')
 valid=known&((code&WAVE_INVALID)==0)&np.isfinite(raw)&np.isfinite(rms)&(rms>0)
 m=np.stack([valid.astype(float),np.where(known,(code&FIT_INVALID)!=0,np.nan),np.where(known,(code&4)!=0,np.nan)],axis=2).reshape(len(raw),12)
 q=np.arcsinh(np.where(valid,raw,np.nan)).astype('float32')
 return m.astype('float32'),q,valid,known

def run(phase):
 cpu,tick=time.process_time(),time.perf_counter();d=load();assert len(d['role'])==89033
 records=freeze(d) if phase=='pilot' else json.loads((OUT/'source_manifest.json').read_text())['records']
 if phase=='pilot':chosen=[records[i] for i in PILOT]
 elif phase=='repeat':chosen=[records[0]]
 else:chosen=[r for r in records if r['active_N']][int(phase.split('_')[1])::BATCHES]
 with ThreadPoolExecutor(max_workers=4 if phase.startswith('batch') else 1) as pool:
  jobs=list(pool.map(lambda r:read_source(r,d,phase),chosen))
 data={k:np.concatenate([v[k] for v,_ in jobs]) for k in jobs[0][0]};summaries=[v for _,v in jobs]
 assert len(set(data['row']))==len(data['row'])
 m,q,valid,known=represent(data['raw'],data['status'],data['rms'])
 cfg=configuration();fit=d['x'][data['row']][:,[cfg['features'].index(f'ML_calo{i}_E_EM_GeV') for i in range(4)]]
 # Distinct getter/source and actual valid-raw/invalid-fitted support establish added measured amplitude.
 recovered=valid&~np.isfinite(fit)
 data.update(m=m,q=q);np.savez_compressed(CACHE/f'{phase}.npz',**data)
 summary=dict(passed=True,phase=phase,N=len(data['row']),source_N=len(chosen),identity_exact_N=sum(v['identity_exact_N'] for v in summaries),
  valid_raw_module_N=int(valid.sum()),raw_valid_fitted_missing_N=int(recovered.sum()),legal_negative_raw_N=int((valid&(data['raw']<0)).sum()),
  raw_minus1_N=int((valid&(data['raw']==-1)).sum()),raw_minus999_N=int((valid&(data['raw']==-999)).sum()),known_status_module_N=int(known.sum()),
  raw_dynamic_range=bool(valid.any() and np.ptp(data['raw'][valid])>0),CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,
  RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,ROOT_read_bytes=sum(v['ROOT_read_bytes'] for v in summaries),sources=summaries,
  scope='No energy labels used; original scalar raw11 and pz0 controls, source-missing kept; source raw semantics explicitly labelled, no ADC inference')
 write(f'{phase}_summary.json',summary);table(f'{phase}_sources.tsv',summaries);print(summary,flush=True)
if __name__=='__main__':run(sys.argv[1])
