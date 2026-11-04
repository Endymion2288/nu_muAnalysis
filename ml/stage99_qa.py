"""Batch-only saved-output interface and fixed train/cal numerical QA."""
import json, time, resource
from pathlib import Path
import numpy as np
from scipy.special import ndtr, logsumexp
R=Path(__file__).resolve().parents[1]; O=R/'workbook/stage99_energy_ml';O.mkdir(parents=True,exist_ok=True)
t=time.perf_counter();c=time.process_time()
paths=['ntuples/energy_ml_stage94/evaluation_input.npz','ntuples/energy_ml_stage94/cal_partition.npz','ml/artifacts/stage94/MDN_heads.npz','ml/artifacts/stage94/point_predictions.npz','ml/artifacts/stage87/predictions.npz','ntuples/energy_ml_stage92/predictions_cal.npz','ntuples/energy_ml_stage92/predictions_test.npz']
schema={}
for path in paths:
 with np.load(R/path) as z:schema[path]={k:dict(shape=list(z[k].shape),dtype=str(z[k].dtype)) for k in z.files}
d=dict(np.load(R/paths[0]));h=dict(np.load(R/paths[2]));raw=dict(np.load(R/paths[3]));ii=np.flatnonzero(d['role']==2)[:40];ih=np.searchsorted(h['row'],d['row'][ii]);assert np.array_equal(h['row'][ih],d['row'][ii])
a=np.log(d['pz'][ii]/.8);ww=[];mm=[];ss=[]
for key in sorted(set(h)-{'row'}):
 x=h[key][ih].astype(float);ww.append(np.exp(x[:,:3]-logsumexp(x[:,:3],axis=1)[:,None])/3);mm.append(x[:,3:6]+a[:,None]);ss.append(.05+np.logaddexp(0,x[:,6:9]))
w=np.column_stack(ww);mu=np.column_stack(mm);sig=np.column_stack(ss);mean=(w*mu).sum(1)
err=float(np.max(abs(mean-raw['E_ensemble'][ii])));assert err<3e-6
# QA checks transform identity and analytic CDF/density against independent scipy normal.
from scipy.stats import norm
T=1.2;b=.02;new=mean[:,None]+b+T*(mu-mean[:,None]);ns=T*sig
e=float(np.max(abs((w*new).sum(1)-(mean+b))));assert e<1e-12
cdf=(w*ndtr((np.log(100)-new)/ns)).sum(1);cdf2=(w*norm.cdf(np.log(100),loc=new,scale=ns)).sum(1);assert np.max(abs(cdf-cdf2))<1e-12
# Freeze pz edges from X only; equal-width physical bins, common reference = pooled train/cal weights.
edges=np.array([50,60,70,80,90,100.]);ref=(d['role']<3)&(d['pz']>50)&(d['pz']<100);mass=np.histogram(d['pz'][ref],edges,weights=d['weight'][ref])[0];mass/=mass.sum()
result=dict(passed=True,identities=40,rows=d['row'][ii].tolist(),schema=schema,decoded_vs_saved_point_max=err,transform_mean_max=e,independent_cdf_max=float(np.max(abs(cdf-cdf2))),pz_edges_GeV=edges.tolist(),X_reference_mass=mass.tolist(),CPU_s=time.process_time()-c,wall_s=time.perf_counter()-t,peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(O/'QA.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
