"""Full identity/measurement QA, train-only templates and source-held controls."""
import json,resource,time
from collections import Counter
import numpy as np
from stage129_energy import ROOT,OUT,CACHE,load,table
from stage129_waveform import templates

CHANNELS=[14,6,7]

def main():
 tick,cpu=time.perf_counter(),time.process_time()
 plan=json.loads((OUT/'extraction_contract.json').read_text());d=load(ROOT/'ntuples/energy_ml_stage119/old_input.npz')
 n=len(d['role']);seen=np.zeros(n,int);status=np.full((n,5),np.nan);times=status.copy();charges=status.copy();present=np.zeros((n,5),bool);rail=np.zeros((n,5),int);track=np.full((n,13),np.nan)
 models={};pool={ch:[] for ch in CHANNELS};byrun={};controls=[];audit=[];rawclosure=[]
 mapping={4:0,5:1,14:2,6:3,7:4}
 for s in plan['requests']:
  a=load(CACHE/f'extract_{s["index"]}.npz');row=a['row'];assert np.array_equal(row,[c['row'] for c in s['cases']]);seen[row]+=1
  assert np.array_equal(d['role'][row],[c['role'] for c in s['cases']]);assert np.array_equal(d['incoming'][row],np.asarray([c['incoming'] for c in s['cases']]))
  status[row]=a['scalar'][:,:,0];charges[row]=a['scalar'][:,:,1];times[row]=a['scalar'][:,:,3]
  matched=np.isclose(a['track'][:,0]/1000,d['pz'][row],rtol=3e-7,atol=3e-5)
  track[row]=np.where(matched[:,None],a['track'],np.nan)
  counts=Counter()
  for j,ch in enumerate(a['channel'][0]):
   ch=int(ch);col=mapping[ch];p=a['present'][:,j];present[row,col]=p;rail[row,col]=((a['adc'][:,j]==0)&p[:,None]).sum(1)
   assert (a['adc'][~p,j]==65535).all();assert (a['adc'][p,j]<=16383).all()
   if ch not in CHANNELS:continue
   waves=a['adc'][:,j];baseline=waves[:,:75].mean(1);peak=baseline-waves[:,390:491].min(1)
   clean=p&(rail[row,col]==0)&(status[row,col]==0)&(peak>20)
   ti=np.flatnonzero(clean&(d['role'][row]==1))
   pool[ch].extend(waves[ti]);byrun.setdefault((s['run'],ch),[]).extend(waves[ti])
   for role in [2,3]:
    for k in np.flatnonzero(clean&(d['role'][row]==role))[:8]:
     controls.append(dict(source=s['index'],run=s['run'],row=int(row[k]),channel=ch,role=role,adc=waves[k],id32=int(a['id32'][k,j])))
     counts[f'control_role{role}_ch{ch}']+=1
  audit.append(dict(source=s['index'],run=s['run'],N=len(row),phys_scalar_N=int(np.isfinite(a['scalar'][:,0,0]).sum()),track_matched_N=int(matched.sum()),**counts))
 assert (seen==1).all(),Counter(seen)
 for ch,waves in pool.items():models[f'pool_{ch}']=templates(waves,[390,491])
 for (run,ch),waves in byrun.items():
  if len(waves)>=50:models[f'{run}_{ch}']=templates(waves,[390,491])
 modelreport=[]
 for key,m in models.items():
  modelreport.append(dict(key=key,controls=m['controls'],sigma_ADC=m['sigma'],rho=m['rho'],baseline_sigma_ADC=m['baseline_sigma'],centre_sample=m['centre']))
 serialized={key:{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in m.items()} for key,m in models.items()}
 (OUT/'templates.json').write_text(json.dumps(serialized,separators=(',',':'))+'\n');table('templates.tsv',modelreport);table('extraction_sources.tsv',audit)
 np.savez_compressed(CACHE/'measurement.npz',status=status,time=times,raw_charge=charges,present=present,rail_samples=rail,track=track)
 # Control source and original role are unchanged. Source-held cal/test are never templates.
 np.savez_compressed(CACHE/'controls.npz',**{k:np.asarray([r[k] for r in controls]) for k in controls[0]})
 pairs=[(0,1),(3,4),(0,3),(1,3)];strict=present&(status==0)&np.isfinite(times)&(times>0)
 rows=[]
 for role in [0,1,2,3]:
  ix=d['role']==role
  for i,j in pairs:
   rows.append(dict(role=role,pair=f'{i}-{j}',N=int(ix.sum()),strict_pair_N=int((ix&strict[:,i]&strict[:,j]).sum()),both_status0_N=int((ix&(status[:,i]==0)&(status[:,j]==0)).sum())))
 table('strict_timing_coverage.tsv',rows)
 for i in [0,48,113]:
  off=json.loads((OUT/f'official_{i}.json').read_text());original=off['original']
  rawclosure.append(dict(source=i,N=len(original),raw_max_abs_pC=max(abs(r['official'][1]-r['phys_raw_pC']) for r in original),fit_max_abs_pC=max(abs(r['official'][2]-r['phys_fit_pC']) for r in original),status_mismatch=sum(r['official'][0]!=r['phys_status'] for r in original),windows=sorted(set(tuple(r['official'][6:8]) for r in original))))
 table('official_replay_closure.tsv',rawclosure)
 report=dict(N=n,roles={str(r):int((d['role']==r).sum()) for r in range(4)},identity_once_all=True,all_sources=len(audit),controls=len(controls),control_parents=len({r['row'] for r in controls}),control_sources=sorted({r['source'] for r in controls}),templates_train_only=True,template_source_test_overlap=0,
  absent_channel_views=int((~present).sum()),unknown_scalar_views=int((~np.isfinite(status)).sum()),actual_rail_waveforms=rail.astype(bool).sum(0).tolist(),strict_status0_N=(status==0).sum(0).tolist(),CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
 (OUT/'measurement_QA.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)

if __name__=='__main__':main()
