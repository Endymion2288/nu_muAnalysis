"""Strict status-zero timing, calibrated with pinned prompt muons only."""
import json,multiprocessing as mp,resource,sys,time
from pathlib import Path
import numpy as np
from audited_features import configuration
from stage129_energy import ROOT,OUT,CACHE,ART,load,table,fit,evaluate

PAIRS=[(0,1),(3,4),(0,3),(1,3)]
Z=np.array([-3122.5,-3101.5,-1790.4,-1620.4,-1598.9])


def design(i,j,q,x,y):
 return np.column_stack([np.ones(len(q)),(x[:,i]+x[:,j])/200,(y[:,i]+y[:,j])/200,1/np.sqrt(q[:,i]),1/np.sqrt(q[:,j])])


def calibration(kind,t,q,valid,x,y,tx,ty,entry):
 records=[]
 for i,j in PAIRS:
  path=(Z[i]-Z[j])*(np.sqrt(1+tx**2+ty**2)-(1 if kind in ['MC','oldMC100012'] else 0))/299.792458
  good=valid[:,i]&valid[:,j]&(q[:,i]>0)&(q[:,j]>0)&np.isfinite(x[:,[i,j]]).all(1)&np.isfinite(y[:,[i,j]]).all(1)&np.isfinite(path)
  train=good&(entry%2==0);test=good&(entry%2==1);record=dict(kind=kind,pair=f'{i}-{j}',train_N=int(train.sum()),validation_N=int(test.sum()),usable=False)
  if train.sum()>=100 and test.sum()>=100:
   with np.errstate(divide='ignore',invalid='ignore'):D=design(i,j,q,x,y)
   a=D[train];target=t[:,i]-t[:,j]-path;coef=np.linalg.lstsq(a,target[train],rcond=None)[0];err=target[test]-D[test]@coef
   condition=float(np.linalg.cond(a));rank=int(np.linalg.matrix_rank(a));median=float(np.median(err));p95=float(np.quantile(abs(err),.95));rms=float(np.sqrt(np.mean(err**2)))
   ranges={k:[float(np.min(v[train])),float(np.max(v[train]))] for k,v in [('qi',q[:,i]),('qj',q[:,j]),('xi',x[:,i]),('yi',y[:,i]),('xj',x[:,j]),('yj',y[:,j])]}
   record.update(coefficient=coef.tolist(),rank=rank,condition=condition,validation_median_ns=median,validation_abs95_ns=p95,validation_RMSE_ns=rms,ranges=ranges,
                 usable=bool(rank==5 and condition<1e6 and abs(median)<.25 and p95<2))
  records.append(record)
 return records


def main():
 tick=time.perf_counter();d=load(ROOT/'ntuples/energy_ml_stage119/old_input.npz');m=load(CACHE/'measurement.npz');n=len(d['role'])
 anchor=json.loads((OUT/'muanchor.json').read_text());nr=len(anchor['records']);t=np.full((nr,5),np.nan);q=t.copy();x=t.copy();y=t.copy();good=np.zeros(t.shape,bool);tx=np.full(nr,np.nan);ty=tx.copy();mapping={4:0,5:1,14:2,6:3,7:4}
 for k,r in enumerate(anchor['records']):
  if 'muon' in r:
   px,py,pz,x0,y0,z0=r['muon'];tx[k]=px/pz;ty[k]=py/pz;x[k]=x0+(Z-z0)*tx[k];y[k]=y0+(Z-z0)*ty[k]
  for wave in r['waves']:
   j=mapping[wave['channel']];a=wave['result'];t[k,j]=a[5];q[k,j]=a[1];good[k,j]=a[0]==0 and np.isfinite(a[5]) and a[5]>0 and a[1]>0
 records=calibration('MC',t,q,good,x,y,tx,ty,np.arange(nr));report=records.copy()
 for index in [1,2]:
  c=load(CACHE/f'mucontrol_{index}.npz');report += calibration('data8006' if index==1 else 'oldMC100012',c['time'],c['charge'],c['valid'],c['x'],c['y'],c['theta_x'],c['theta_y'],np.arange(len(c['time'])))
 # Freeze all coefficients and validation decisions before nu timing application/fit.
 (OUT/'timing_calibration.json').write_text(json.dumps(report,indent=2)+'\n');table('timing_calibration.tsv',[{k:v for k,v in r.items() if k not in ['coefficient','ranges']} for r in report])
 if sys.argv[1]=='1':return
 nt=np.full((n,5),np.nan);nq=nt.copy();nv=np.zeros(nt.shape,bool);replaycost=[]
 for batch in range(20):
  path=CACHE/f'timereplay_{batch}.npz'
  if not path.exists():path=Path('/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage129')/path.name
  a=load(path)
  for channel,j in mapping.items():
   use=a['channel']==channel;row=a['row'][use];assert (m['status'][row,j]==0).all();good=(a['new_status'][use]==0)&np.isfinite(a['new_time_ns'][use])&(a['new_time_ns'][use]>0)
   nt[row,j]=np.where(good,a['new_time_ns'][use],np.nan);nq[row,j]=a['new_raw_pC'][use];nv[row,j]=good
 original=m['present']&(m['status']==0)&np.isfinite(m['time'])&(m['time']>0)
 track=m['track'];x=track[:,[1,1,5,9,9]];y=track[:,[2,2,6,10,10]];tx=np.tan(track[:,3]);ty=np.tan(track[:,4]);flags=[];values=[];names=[];support=[]
 for i,j in PAIRS:
  tag=f'{i}_{j}';cal=next(r for r in records if r['pair']==f'{i}-{j}');strict=original[:,i]&original[:,j];both=strict&nv[:,i]&nv[:,j]
  apply=both&np.isfinite(x[:,[i,j]]).all(1)&np.isfinite(y[:,[i,j]]).all(1)&np.isfinite(tx)&np.isfinite(ty)
  for key,v in [('qi',nq[:,i]),('qj',nq[:,j]),('xi',x[:,i]),('yi',y[:,i]),('xj',x[:,j]),('yj',y[:,j])]:
   if cal['usable']:
    low,high=cal['ranges'][key];apply &= (v>=low)&(v<=high)
   else:apply &= False
  delta=np.full(n,np.nan)
  if apply.any():
   D=design(i,j,nq[apply],x[apply],y[apply]);path=(Z[i]-Z[j])*(np.sqrt(1+tx[apply]**2+ty[apply]**2)-1)/299.792458
   delta[apply]=nt[apply,i]-nt[apply,j]-path-D@np.asarray(cal['coefficient'])
  assert not np.isfinite(delta[~both]).any()
  flags.extend([strict,both,apply]);values.append(delta);names.extend([f'timing_{tag}_{s}' for s in ['old_strict','replay_strict','calibrated_available']])
  for role in [1,2,3]:
   ix=d['role']==role;support.append(dict(role=role,pair=tag,N=int(ix.sum()),original_strict=int((ix&strict).sum()),replay_strict=int((ix&both).sum()),calibrated_range=int((ix&apply).sum())))
 flags=np.column_stack(flags).astype('float32');values=np.column_stack(values).astype('float32');table('timing_application_support.tsv',support)
 np.savez_compressed(CACHE/'timing_features.npz',valid=flags,features=values)
 base=configuration()['features'];delta_names=[f'calibrated_dt_{i}_{j}_ns' for i,j in PAIRS]
 np.savez_compressed(ART/'timing_X_prediction.npz',**load(ART/'depth_X_prediction.npz'))
 tasks=[('timing','V',np.column_stack([d['x'],flags]),base+names,d),('timing','T',np.column_stack([d['x'],flags,values]),base+names+delta_names,d)]
 with mp.get_context('fork').Pool(2) as pool:fits=pool.map(fit,tasks)
 (OUT/'timing_fits.json').write_text(json.dumps(fits,indent=2)+'\n');evaluate('timing',d,['X','V','T'])
 (OUT/'timing_cost.json').write_text(json.dumps(dict(wall_s=time.perf_counter()-tick,children_CPU_s=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime),indent=2)+'\n')

if __name__=='__main__':main()
