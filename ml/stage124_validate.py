"""Independent row-space validation of locked Stage124 energy/tail results."""
import csv,json,time,resource
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'workbook/stage124_energy_ml'
def read(path):
 with np.load(ROOT/path) as z:return {k:z[k] for k in z.files}
def rows(name):return list(csv.DictReader((OUT/name).open(),delimiter='\t'))
def interval(v):
 v=v[np.isfinite(v)];return np.quantile(v,[.025,.975]) if len(v)>=475 else [None,None]
def main():
 cpu=time.process_time();tick=time.perf_counter()
 d=read('ntuples/energy_ml_stage124/comparison_input.npz');p=read('ml/artifacts/stage124/predictions.npz');old=read('ml/artifacts/stage87/predictions.npz')
 assert len(d['role'])==89033 and [(d['role']==r).sum() for r in range(4)]==[17657,46575,11612,13189]
 active=d['role']>0
 np.testing.assert_array_equal(p['direct_cal'][active],old['direct_cal'])
 assert all(np.isnan(v[~active]).all() for v in p.values())
 # No incoming proxy crosses roles. Quarantined views have zero prediction.
 keys=[{tuple(v) for v in d['incoming'][d['role']==r]} for r in [1,2,3]]
 assert not any(keys[i]&keys[j] for i in range(3) for j in range(i))
 assert d['XZ'].shape==(89033,119)
 assert all(np.isfinite(v[active]).all() for v in p.values())
 np.testing.assert_array_equal(d['XZ'][:,:62],d['x'])
 fc=json.loads((OUT/'feature_contract.json').read_text());assert len(fc['Z'])==56
 assert len({f['name'] for f in fc['Z']})==56
 bad=[f['name'] for f in fc['Z'] if any(v in f['name'] for v in ['truth','pz1','p0_','p1_','charge'])];assert not bad
 pair=rows('paired.tsv');point=rows('metrics.tsv');checks=[]
 for role in [2,3]:
  ix=np.flatnonzero(d['role']==role);inc=d['incoming'][ix];_,first,gid,count=np.unique(inc,axis=0,return_index=True,return_inverse=True,return_counts=True)
  w=1/count[gid];np.testing.assert_allclose(w,d['weight'][ix],atol=1e-12,rtol=0)
  draw=np.zeros((500,len(first)),np.int16);rng=np.random.default_rng(20261106124+role)
  for component in sorted(set(d['component'][ix[first]])):
   u=np.flatnonzero(d['component'][ix[first]]==component);draw[:,u]=rng.multinomial(len(u),np.full(len(u),1/len(u)),size=500)
  e=d['truth_E_GeV'][ix];pz=d['pz'][ix];y=d['y_lepton'][ix];physical=d['primary_valid'][ix].astype(bool)&np.isfinite(y)&(y>=0)&(y<1)
  layers={'E50_100':(e>=50)&(e<100),'E100_200':(e>=100)&(e<200),'all':np.ones(len(ix),bool),'E200_inf':e>=200,'pz50_100':(pz>=50)&(pz<100),'pz50_100_trueE200':(pz>=50)&(pz<100)&(e>=200),'high_y':physical&(y>=.8),'unconfirmed':~d['confirmed'][ix].astype(bool),'input_missing':np.isnan(d['x'][ix]).any(1),'highE':e>=1000,'upstream':d['vertex_z_mm'][ix]<-2200}
  for layer,m in layers.items():
   if not m.any():continue
   rr=ix[m];ww=w[m];rw=draw[:,gid[m]]*ww;den=rw.sum(1);good=den>0;error=0.;ncheck=0
   errs={n:p[n][rr]-np.log(e[m]) for n in p};rel={n:np.expm1(v) for n,v in errs.items()}
   for row in [r for r in pair if int(r['role'])==role and r['stratum']==layer]:
    a,b=row['candidate'],row['reference'];aa,bb=errs[a]**2,errs[b]**2
    central=np.sqrt(np.average(aa,weights=ww)/np.average(bb,weights=ww));error=max(error,abs(central-float(row['RMSE_ratio'])));ncheck+=1
    ci=interval(np.sqrt((rw@aa)/(rw@bb)))
    if row['low95']:
     error=max(error,abs(ci[0]-float(row['low95'])),abs(ci[1]-float(row['high95'])));ncheck+=2
    for sign in ['total','positive','negative']:
     fa=abs(rel[a])>.5 if sign=='total' else rel[a]>.5 if sign=='positive' else rel[a]<-.5
     fb=abs(rel[b])>.5 if sign=='total' else rel[b]>.5 if sign=='positive' else rel[b]<-.5
     diff=fa.astype(float)-fb.astype(float);estimate=100*np.average(diff,weights=ww);ci=interval(100*(rw[good]@diff)/den[good])
     error=max(error,abs(estimate-float(row[sign+'_tail_delta_pp'])));ncheck+=1
     if row[sign+'_tail_low95_pp']:
      error=max(error,abs(ci[0]-float(row[sign+'_tail_low95_pp'])),abs(ci[1]-float(row[sign+'_tail_high95_pp'])));ncheck+=2
   for row in [r for r in point if int(r['role'])==role and r['stratum']==layer]:
    a=row['model'];order=np.argsort(rel[a],kind='stable');q=np.interp([.16,.5,.84],(np.cumsum(ww[order])-.5*ww[order])/ww.sum(),rel[a][order]);v=rel[a]
    metric={'log_RMSE':np.sqrt(np.average(errs[a]**2,weights=ww)),'mean_bias_pct':100*np.average(v,weights=ww),'median_bias_pct':100*q[1],'R68_pct':50*(q[2]-q[0]),'tail50_pct':100*np.average(abs(v)>.5,weights=ww),'positive_tail50_pct':100*np.average(v>.5,weights=ww),'negative_tail50_pct':100*np.average(v<-.5,weights=ww)}
    for k,val in metric.items():error=max(error,abs(val-float(row[k])));ncheck+=1
   assert error<1e-10,(role,layer,error)
   checks.append(dict(role=role,stratum=layer,scalar_checks=ncheck,max_abs_difference=error))
 with (OUT/'independent_validation.tsv').open('w') as f:
  wtr=csv.DictWriter(f,fieldnames=list(checks[0]),delimiter='\t',lineterminator='\n');wtr.writeheader();wtr.writerows(checks)
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(1,2,figsize=(10,3.7),layout='constrained')
 chosen=['E50_100','E100_200','all','pz50_100_trueE200','high_y'];labels=['50–100 GeV','100–200 GeV','All','Low pz, high E','High y'];models=['traditional','direct_cal','X','XZ']
 for j,n in enumerate(models):
  v=[float(next(r for r in point if r['role']=='3' and r['stratum']==k and r['model']==n)['log_RMSE']) for k in chosen]
  axes[0].plot(range(len(v)),v,'o-',label=n)
 axes[0].set_xticks(range(len(labels)),labels,rotation=25,ha='right');axes[0].set_ylabel('log-energy RMSE');axes[0].set_yscale('log');axes[0].legend(fontsize=8)
 for role,offset in [(2,-.07),(3,.07)]:
  r=[next(r for r in pair if r['role']==str(role) and r['stratum']==k and r['candidate']=='XZ' and r['reference']=='X') for k in chosen]
  v=np.array([float(x['RMSE_ratio']) for x in r]);lo=np.array([float(x['low95']) for x in r]);hi=np.array([float(x['high95']) for x in r]);axes[1].errorbar(np.arange(5)+offset,v,yerr=[v-lo,hi-v],fmt='o',label='cal' if role==2 else 'developed test')
 axes[1].axhline(1,color='gray',lw=1);axes[1].set_xticks(range(5),labels,rotation=25,ha='right');axes[1].set_ylabel('XZ / X RMSE, conditional 95% CI');axes[1].legend(fontsize=8)
 fig.savefig(OUT/'native_energy_comparison.png',dpi=160);plt.close(fig)
 result=dict(passed=True,scalar_checks=sum(r['scalar_checks'] for r in checks),max_abs_difference=max(r['max_abs_difference'] for r in checks),role_counts_preserved=True,incoming_role_overlap=0,quarantine_predictions=0,reserved_predictions=0,native_available_N=int(d['z_available'].sum()),CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
 (OUT/'validation_summary.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)
if __name__=='__main__':main()
