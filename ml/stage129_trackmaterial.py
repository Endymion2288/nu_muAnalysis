"""Full-support measured-IFT geometric compatibility and conditional material scores.

The three momentum hypotheses are uncertainty diagnostics, never measured hadron
momenta or calibrated vertex posteriors. All unavailable parents remain in X.
"""
import csv,gzip,json,multiprocessing as mp,resource,time
from pathlib import Path
import numpy as np
from audited_features import configuration
from stage129_energy import ROOT,OUT,CACHE,ART,load,table,fit,evaluate


def cumulative(z,segments,key):
 low=np.asarray([r['low'] for r in segments]);high=np.asarray([r['high'] for r in segments]);length=np.asarray([r[key] for r in segments])
 return np.sum(np.clip(np.asarray(z)[...,None]-low,0,high-low)/length,axis=-1)


def features(record,segments):
 g=record['tracks']['Segments'];selected=[];owned=set();candidates=[]
 for value,prds in zip(g.get('values',[]),g.get('prds',[])):
  v=np.asarray(value);c=v[12:].reshape(4,4)
  if not (v[6:8]==1).all() or not np.isfinite(c).all() or np.linalg.eigvalsh(c).min()<=0:continue
  if v[8]!=1 or v[11]<=0 or v[9]<5:continue
  candidates.append((v[10]/v[11],-len(prds),v,set(prds)))
 for _,__,v,prds in sorted(candidates,key=lambda t:(t[0],t[1])):
  if owned&prds:continue
  selected.append(v);owned|=prds
  if len(selected)==6:break
 flags=[float(g['available']),float(len(selected)>=2),float(len(selected))]
 if len(selected)<2:return flags,[np.nan]*18
 zgrid=-3000+(np.arange(64)+.5)*1050/64;stats=[]
 values=np.asarray(selected);cov=values[:,12:].reshape(-1,4,4);position=values[:,:2];slopes=values[:,3:5]
 atgrid=cumulative(zgrid,segments,'X0');atend=cumulative(values[:,2],segments,'X0')
 material=cumulative(-1300,segments,'lambdaI')-cumulative(zgrid,segments,'lambdaI')
 materialX=cumulative(-1300,segments,'X0')-atgrid
 for momentum in [1.,10.,100.]:
  chi=[]
  for zi,z in enumerate(zgrid):
   length=values[:,2]-z;point=position-length[:,None]*slopes
   h=np.zeros((len(values),2,4));h[:,0,0]=1;h[:,1,1]=1;h[:,0,2]=-length;h[:,1,3]=-length
   c=h@cov@h.transpose(0,2,1)
   x0=atend-atgrid[zi]
   theta2=(.0136/momentum)**2*x0*(1+.038*np.log(np.maximum(x0,1e-12)))**2
   c+=np.eye(2)[None]*(theta2*length**2/3)[:,None,None]
   w=np.linalg.inv(c);sw=w.sum(0);mean=np.linalg.solve(sw,np.einsum('ijk,ik->j',w,point));delta=point-mean
   chi.append(float(np.einsum('ij,ijk,ik->',delta,w,delta)))
  chi=np.asarray(chi);score=np.exp(-.5*(chi-chi.min()));score/=score.sum();mean=float(score@zgrid);sd=float(np.sqrt(score@(zgrid-mean)**2))
  stats.extend([mean,sd,float(chi.min()/max(1,2*len(values)-2)),float(score@material),float(score@materialX),float(np.exp(-.5*chi.min()))])
 return flags,stats


def main():
 tick,cpu=time.perf_counter(),time.process_time();d=load(ROOT/'ntuples/energy_ml_stage119/old_input.npz');n=len(d['role']);flags=np.zeros((n,3));x=np.full((n,18),np.nan);seen=np.zeros(n,int)
 raw=list(csv.DictReader((OUT/'material_segments.tsv').open(),delimiter='\t'));print('MATERIAL_FIELDS',raw[0].keys(),flush=True)
 # Keep exact geometry lengths; no material or vertex-truth fit.
 segments=[dict(low=float(r['low_mm']),high=float(r['high_mm']),X0=float(r['X0_mm']),lambdaI=float(r['lambdaI_mm'])) for r in raw]
 for i in range(1000,1070):
  path=CACHE/f'trackcov_{i}.json.gz'
  if not path.exists():path=Path('/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage129')/path.name
  with gzip.open(path,'rt') as f:records=json.load(f)
  for r in records:
   row=r['row'];seen[row]+=1;flags[row],x[row]=features(r,segments)
 assert (seen==1).all();names=[]
 for p in [1,10,100]:names += [f'IFT_p{p}_{key}' for key in ['score_z_mm','score_z_sd_mm','minchi2_ndof','remaining_lambdaI','remaining_X0','compatibility']]
 np.savez_compressed(CACHE/'trackmaterial_features.npz',valid=flags,features=x,names=names)
 support=[]
 for role in [1,2,3]:
  for name,mask in [('all',np.ones(n,bool)),('E50_100',(d['truth_E_GeV']>=50)&(d['truth_E_GeV']<100)),('E100_200',(d['truth_E_GeV']>=100)&(d['truth_E_GeV']<200))]:
   ix=(d['role']==role)&mask;valid=ix&(flags[:,1]==1)
   support.append(dict(role=role,stratum=name,N=int(ix.sum()),two_disjoint_IFT=int(valid.sum()),conditional_p10_z_RMSE_mm=float(np.sqrt(np.mean((x[valid,6]-d['vertex_z_mm'][valid])**2))) if valid.any() else None,conditional_p10_width_mean_mm=float(np.mean(x[valid,7])) if valid.any() else None))
 table('trackmaterial_observable_support.tsv',support)
 base=configuration()['features'];flag_names=['IFT_native_available','IFT_two_disjoint','IFT_disjoint_N']
 for arm in ['X']:
  old=load(ART/f'depth_{arm}_prediction.npz');np.savez_compressed(ART/f'trackmaterial_{arm}_prediction.npz',**old)
 tasks=[('trackmaterial','V',np.column_stack([d['x'],flags]).astype('float32'),base+flag_names,d),('trackmaterial','G',np.column_stack([d['x'],flags,x]).astype('float32'),base+flag_names+names,d)]
 with mp.get_context('fork').Pool(2) as pool:fits=pool.map(fit,tasks)
 (OUT/'trackmaterial_fits.json').write_text(json.dumps(fits,indent=2)+'\n');evaluate('trackmaterial',d,['X','V','G'])
 (OUT/'trackmaterial_cost.json').write_text(json.dumps(dict(CPU_s=time.process_time()-cpu,children_CPU_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),indent=2)+'\n')

if __name__=='__main__':main()
