"""Fixed full-support recovery; jobs own disjoint original source batches."""
import json,multiprocessing as mp,resource,sys,time
from pathlib import Path
import numpy as np
from stage129_energy import OUT,CACHE,load
from stage129_waveform import recover


def model_for(models,run,ch):
 return models.get(f'{run}_{ch}',models[f'pool_{ch}'])


def read_models():
 models=json.loads((OUT/'templates.json').read_text())
 for m in models.values():
  m['mean']=np.asarray(m['mean']);m['pc']=np.asarray(m['pc'])
 return models


def work(task):
 adc,model=task
 return recover(adc,model)


def main():
 tick,cpu=time.perf_counter(),time.process_time();index=int(sys.argv[1]);models=read_models()
 plan=json.loads((OUT/'extraction_contract.json').read_text())
 if index==-1:
  controls=load(CACHE/'controls.npz');tasks=[];meta=[]
  for i in range(len(controls['row'])):
   adc=controls['adc'][i].astype(int);base=adc[:75].mean();peak=base-adc.min();run=int(controls['run'][i]);ch=int(controls['channel'][i]);target=.04*2/16.384*(base*101-adc[390:491].sum())
   for frac in [.75,.5,.25]:
    shift=int(np.floor(base-frac*peak));tasks.append((np.maximum(adc-shift,0),model_for(models,run,ch)))
    meta.append(dict(control=i,row=int(controls['row'][i]),source=int(controls['source'][i]),role=int(controls['role'][i]),channel=ch,fraction=frac,ADC_shift=shift,target_pC=target))
  with mp.get_context('fork').Pool(4) as pool:results=pool.map(work,tasks,chunksize=16)
  records=[dict(**m,**r) for m,r in zip(meta,results)]
  np.savez_compressed(CACHE/'artificial_recovery.npz',**{k:np.asarray([r[k] for r in records]) for k in records[0]})
  name='artificial'
 else:
  records=[];tasks=[];offset=[];name=f'recover_{index}'
  # Twenty disjoint jobs, each14 original source files, no repeated fitting.
  for source in plan['requests'][index*14:(index+1)*14]:
   path=CACHE/f'extract_{source["index"]}.npz'
   if not path.exists():path=Path('/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage129')/path.name
   a=load(path)
   for j,ch in enumerate(a['channel'][0]):
    ch=int(ch)
    if ch not in [14,6,7]:continue
    for i,row in enumerate(a['row']):
     if not a['present'][i,j] or not (a['adc'][i,j]==0).any():continue
     offset.append(dict(row=int(row),channel=ch,source=source['index']))
     tasks.append((a['adc'][i,j],model_for(models,source['run'],ch)))
  with mp.get_context('fork').Pool(4) as pool:results=pool.map(work,tasks,chunksize=16)
  records=[dict(**m,**r) for m,r in zip(offset,results)]
  np.savez_compressed(CACHE/f'{name}.npz',**{k:np.asarray([r[k] for r in records]) for k in records[0]})
 report=dict(index=index,fits=len(records),available=sum(r['available'] for r in records),reasons={k:sum(r['profile_status']==k for r in records) for k in sorted({r['profile_status'] for r in records})},wall_s=time.perf_counter()-tick,parent_CPU_s=time.process_time()-cpu,children_CPU_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
 (OUT/f'{name}_summary.json').write_text(json.dumps(report,indent=2)+'\n');print(report,flush=True)

if __name__=='__main__':main()
