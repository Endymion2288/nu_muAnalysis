"""Stage99 frozen saved-output diagnostics and one scalar NLL calibration (batch)."""
import csv,json,math,time,resource,multiprocessing as mp
from pathlib import Path
import numpy as np
from scipy.special import ndtr,logsumexp
from scipy.optimize import minimize
R=Path(__file__).resolve().parents[1];O=R/'workbook/stage99_energy_ml'
def load(p):
 with np.load(R/p) as z:return {k:z[k] for k in z.files}
def save(n,x): (O/n).write_text(json.dumps(x,indent=2,allow_nan=False))
def table(n,rows):
 dest=(R/'ntuples/energy_ml_stage99'/n) if n in ['B_collection_features.tsv','B_identities.tsv','B_classifier_predictions.tsv','B_QA_identities.tsv'] else O/n
 dest.parent.mkdir(parents=True,exist_ok=True)
 with dest.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for x in rows for k in x)),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
def avg(v,w):return float(np.average(v,weights=w))
def ci(x):
 x=np.asarray(x);x=x[np.isfinite(x)];return [float(v) for v in np.quantile(x,[.025,.975])] if len(x) else [None,None]
def masks(d):
 e,p=d['truth_E_GeV'],d['pz'];v=d['label_physical'];f=d['y_lepton'];other=d['input_missing']|d['wave_invalid']|d['fit_failure']|d['calo_invalid']
 r=dict(all=np.ones(len(e),bool),E50_100=(e>=50)&(e<100),E100_200=(e>=100)&(e<200),E200_inf=e>=200,pz50_100=p<100,pz50_100_trueE200=(p<100)&(e>=200),high_y=v&(f>=.8),unconfirmed=~d['confirmed'],input_missing=d['input_missing'],fit_failure=d['fit_failure'],response_nominal=~other,negative_valid_raw=d['negative_valid_raw'],confirmed_low_transfer=d['confirmed']&v&(f<.2),X_pz50_100=p<100,X_pz100_200=(p>=100)&(p<200),X_pz200_plus=p>=200,X_status_valid=~other,X_status_other=other)
 for lo,hi in [(200,400),(400,800),(800,1600),(1600,3200),(3200,6400),(6400,np.inf)]:r[f'E{lo}_{"inf" if np.isinf(hi) else hi}']=(e>=lo)&(e<hi)
 for a in ['calo','activity']:
  for b in [-1,0,1,2]:r[f'X_{a}_{b}']=d['X_'+a]==b
 return r
def boot(d,seed):
 key,first,gid=np.unique(d['key_id'],return_index=True,return_inverse=True);comp=d['component'][first];rng=np.random.default_rng(seed);draw=np.zeros((500,len(key)),np.int16)
 for c in sorted(set(comp)):
  ix=np.flatnonzero(comp==c);draw[:,ix]=rng.multinomial(len(ix),np.full(len(ix),1/len(ix)),size=500)
 return gid,draw

def dist(w,mu,sig,y):
 def cdf(z):return (w*ndtr((z[:,None]-mu)/sig)).sum(1)
 q=[];res=0
 for p in [.05,.16,.5,.84,.95]:
  lo=np.min(mu-12*sig,axis=1);hi=np.max(mu+12*sig,axis=1)
  for _ in range(55):
   mid=(lo+hi)/2;go=cdf(mid)>=p;hi=np.where(go,mid,hi);lo=np.where(go,lo,mid)
  z=(hi+lo)/2;res=max(res,float(np.max(abs(cdf(z)-p))));q.append(z)
 ld=logsumexp(np.log(w)-np.log(sig)-.5*((y[:,None]-mu)/sig)**2-.5*math.log(2*math.pi),axis=1)
 assert res<1e-10 and np.isfinite(ld).all()
 return dict(q=np.column_stack(q),PIT=cdf(y),NLL=-ld,root=res)

def curve(s,label,w):
 order=np.argsort(-s,kind='stable');s=s[order];label=label[order];w=w[order];ends=np.r_[np.flatnonzero(np.diff(s)!=0),len(s)-1]
 fp=np.r_[0,np.cumsum(w*(label==0))[ends]];tp=np.r_[0,np.cumsum(w*(label==1))[ends]]
 fp/=fp[-1];tp/=tp[-1];auc=float(np.trapezoid(tp,fp));x=np.r_[fp[fp<.1],.1];y=np.r_[tp[fp<.1],np.interp(.1,fp,tp)];pauc=float(np.trapezoid(y,x)/.1)
 return fp,tp,auc,pauc

def main():
 assert not (O/'calibration.json').exists(), 'Stage99 permits exactly one scalar fit'
 start=time.perf_counter();cpu=time.process_time();qa=json.loads((O/'QA.json').read_text());assert qa['passed']
 d=load('ntuples/energy_ml_stage94/evaluation_input.npz');raw=load('ml/artifacts/stage94/point_predictions.npz');h=load('ml/artifacts/stage94/MDN_heads.npz');base=load('ml/artifacts/stage87/predictions.npz');part=load('ntuples/energy_ml_stage94/cal_partition.npz')
 assert np.array_equal(d['row'],raw['row']);ib=np.searchsorted(base['row'],d['row']);assert np.array_equal(base['row'][ib],d['row']);ih=np.searchsorted(d['row'],h['row']);assert np.array_equal(d['row'][ih],h['row'])
 n=len(d['row']);m=np.log(d['pz']/.8);y=np.log(d['truth_E_GeV']);weight=d['weight'];role=d['role'];subrole=np.zeros(n,int);pw=np.zeros(n);cal=np.flatnonzero(role==2);ip=np.searchsorted(part['row'],d['row'][cal]);assert np.array_equal(part['row'][ip],d['row'][cal]);subrole[cal]=part['subrole'][ip];pw[cal]=part['weight'][ip]
 b={x['model']:float(x['offset_logE']) for x in csv.DictReader((R/'workbook/stage94_energy_ml/offsets.tsv').open(),delimiter='\t')}['E_ensemble']
 ww=[];mm=[];ss=[]
 for key in sorted(set(h)-{'row'}):
  x=h[key].astype(float);ww.append(np.exp(x[:,:3]-logsumexp(x[:,:3],axis=1)[:,None])/3);mm.append(x[:,3:6]+m[ih,None]);ss.append(.05+np.logaddexp(0,x[:,6:9]))
 w=np.column_stack(ww);mu=np.column_stack(mm);sig=np.column_stack(ss);mean=(w*mu).sum(1);assert np.max(abs(mean-raw['E_ensemble'][ih]))<3e-6
 post=subrole[ih]==2
 def objective(t):
  T=float(t[0]);mm=mean[:,None]+b+T*(mu-mean[:,None]);s=T*sig
  ld=logsumexp(np.log(w[post])-np.log(s[post])-.5*((y[ih][post,None]-mm[post])/s[post])**2-.5*math.log(2*math.pi),axis=1)
  return -np.average(ld,weights=pw[ih][post])
 opt=minimize(objective,[1.],method='L-BFGS-B',bounds=[(.5,3)],options=dict(maxiter=100,ftol=1e-12,gtol=1e-8));T=float(opt.x[0]);assert opt.success
 new=mean[:,None]+b+T*(mu-mean[:,None]);assert np.max(abs((w*new).sum(1)-(mean+b)))<1e-12
 point=raw['E_ensemble'].astype(float)+b;fixed=point.copy();assert np.array_equal(fixed,point)
 save('calibration.json',dict(T=T,b_fixed=b,success=bool(opt.success),message=str(opt.message),iterations=int(opt.nit),evaluations=int(opt.nfev),boundary_hit=bool(abs(T-.5)<1e-6 or abs(T-3)<1e-6),cal_post_N=int(post.sum()),cal_post_weight=float(pw[ih][post].sum()),NLL_before=float(objective([1.])),NLL_after=float(opt.fun),point_exact_unchanged=True,decoded_mean_vs_saved_max=float(np.max(abs(mean-raw['E_ensemble'][ih]))),algebraic_mean_transform_max=float(np.max(abs((w*new).sum(1)-mean-b)))))
 # Two independent analytic role distributions use allocated CPU workers; no network or ROOT.
 jobs=[]
 for code in [2,3]:
  ix=np.flatnonzero(role[ih]==code)
  jobs.extend([(w[ix],mu[ix]+b,sig[ix],y[ih][ix]),(w[ix],new[ix],sig[ix]*T,y[ih][ix])])
 with mp.get_context('fork').Pool(4) as pool:probs=pool.starmap(dist,jobs)
 policies={'traditional':m,'direct_cal':base['direct_cal'][ib],'bounded_cal':base['bounded_cal'][ib],'E94_ensemble':point}
 oldmass={};saved_schema={}
 oldpoint=np.full(n,np.nan)
 for name,code in [('cal',2),('test',3)]:
  old=load(f'ntuples/energy_ml_stage92/predictions_{name}.npz');idx=np.flatnonzero(role==code);assert np.array_equal(d['row'][idx],old['row']);oldpoint[idx]=old['accurate_quantiles'][:,2];saved_schema[name]={k:list(v.shape) for k,v in old.items()}
  # accurate_F stores the raw CDF on the exact EDGES in posterior_numerics.py.
  # Apply the old fixed nominal prior to its saved bin masses, matching summary().
  if 'accurate_F' in old:
   F=old['accurate_F'];assert F.shape==(len(idx),10) and old['numerical_certified'].all()
   ratio=np.array(json.loads((R/'workbook/stage87_energy_ml/prior.json').read_text())['ratios']['nominal'])
   mass=np.diff(F)*ratio;low=mass[:,1];high=mass[:,3:].sum(1)
   oldmass[code]=np.divide(high,low+high,out=np.full(len(high),np.nan),where=low+high>0)
 policies['posterior92']=oldpoint
 save('stage92_mass_availability.json',dict(available_roles=list(oldmass),saved_schema=saved_schema,new_integrations=0))
 # Stage94 analytic raw calibrated distribution, before the new T; ranking protocol is fixed.
 def cdf(z):return (w*ndtr((math.log(z)-mu-b)/sig)).sum(1)
 low=cdf(100)-cdf(50);high=1-cdf(200);q=np.divide(high,low+high,out=np.full(len(high),np.nan),where=low+high>0)
 score={'pz0':d['pz'].astype(float),'direct_cal_saved':policies['direct_cal'],'E94_mass_ratio':np.full(n,np.nan)};score['E94_mass_ratio'][ih]=q
 if len(oldmass)==2:
  score['stage92_mass_ratio']=np.full(n,np.nan)
  for code in [2,3]:score['stage92_mass_ratio'][role==code]=oldmass[code]
 risk=[];decomp=[];probrows=[];pitrows=[];support=[];rocrows=[];wp=[];curve_rows=[];gaps=[];threshold_rows=[]
 bins=np.searchsorted(np.array(qa['pz_edges_GeV']),d['pz'],side='right')-1;ref=np.array(qa['X_reference_mass']);L=(d['truth_E_GeV']>=50)&(d['truth_E_GeV']<100);H=d['truth_E_GeV']>=200;domain=(d['pz']>50)&(d['pz']<100);label=np.where(H,1,0)
 # Freeze one global threshold per score/alpha using standardized cal_select L only.
 select=(subrole==1)&domain
 thresholds={}
 for name,s in score.items():
  valid=select&np.isfinite(s);common=np.array([np.any(valid&L&(bins==j)) and np.any(valid&H&(bins==j)) for j in range(5)]);r=ref*common;r/=r.sum();lw=np.zeros(n)
  for j in np.flatnonzero(common):
   ix=valid&L&(bins==j);lw[ix]=weight[ix]*r[j]/weight[ix].sum()
  v=np.unique(s[lw>0]);fp=np.array([lw[s>t].sum() for t in v])
  for alpha in [.02,.05,.1]:
   t=float(v[np.flatnonzero(fp<=alpha+1e-14)[0]]);thresholds[name,alpha]=t;threshold_rows.append(dict(score=name,alpha=alpha,threshold=t,strict_greater=True,cal_select_FPR=float(lw[s>t].sum()),L_N=int((lw>0).sum()),common_bins=','.join(map(str,np.flatnonzero(common)))))
 table('thresholds.tsv',threshold_rows)
 for code,role_name in [(2,'cal'),(3,'test')]:
  use=np.flatnonzero(role==code);dd={k:v[use] for k,v in d.items()};gid,draw=boot(dd,2026110499+code);dw=draw[:,gid].astype(float);W=weight[use];Y=y[use];M=m[use];groups=masks(dd)
  def bavg(v,z):
   a=dw[:,z]*W[z];den=a.sum(1);return np.divide(a@v[z],den,out=np.full(len(den),np.nan),where=den>0)
  for group,z in groups.items():
   if not z.any():continue
   wwz=W[z];N=int(z.sum());supp=dict(role=role_name,stratum=group,N=N,incoming=int(len(np.unique(dd['key_id'][z]))),weight_sum=float(wwz.sum()))
   for name,P in policies.items():
    P=P[use];e=P-Y;c=P-M;e0=M-Y;loss=e*e
    err=float(np.max(abs(loss-e0*e0-c*c-2*e0*c)[z]));assert err<1e-12
    bs=bavg(c*c+2*e0*c,z);bounds=ci(bs)
    decomp.append(dict(**supp,model=name,E_c2=avg(c[z]**2,wwz),two_E_e0c=2*avg(e0[z]*c[z],wwz),risk_delta=avg(loss[z]-e0[z]**2,wwz),delta_low95=bounds[0],delta_high95=bounds[1],identity_max_abs=err))
    rel=np.expm1(e[z]);risk.append(dict(**supp,model=name,log_RMSE=math.sqrt(avg(loss[z],wwz)),total_tail_pct=100*avg(abs(rel)>.5,wwz),positive_tail_pct=100*avg(rel>.5,wwz),negative_tail_pct=100*avg(rel<-.5,wwz)))
   for j,p in enumerate(probs[(code-2)*2:(code-2)*2+2]):
    qv=p['q'];pit=p['PIT'];nll=p['NLL'];stage='before' if j==0 else 'after'
    nci=ci(bavg(nll,z));pci=ci(bavg(pit,z));rr=dict(**supp,stage=stage,NLL=avg(nll[z],wwz),NLL_low95=nci[0],NLL_high95=nci[1],mean_PIT=avg(pit[z],wwz),PIT_low95=pci[0],PIT_high95=pci[1],uniformity_required=(group=='all' or group.startswith('X_')))
    for lev,lo,hi in [(68,1,3),(90,0,4)]:
     flag=((Y>=qv[:,lo])&(Y<=qv[:,hi])).astype(float);bounds=ci(bavg(flag,z));rr.update({f'coverage{lev}_pct':100*avg(flag[z],wwz),f'coverage{lev}_low95_pct':100*bounds[0],f'coverage{lev}_high95_pct':100*bounds[1],f'width{lev}_logE':avg(qv[z,hi]-qv[z,lo],wwz)})
    probrows.append(rr)
    for bidx in range(10):pitrows.append(dict(**supp,stage=stage,PIT_bin=bidx,fraction=avg((np.minimum((pit[z]*10).astype(int),9)==bidx).astype(float),wwz)))
  bounds=ci(bavg(probs[(code-2)*2+1]['NLL']-probs[(code-2)*2]['NLL'],np.ones(len(use),bool)))
  save(f'{role_name}_probability_change.json',dict(NLL_delta_low95=bounds[0],NLL_delta_high95=bounds[1],quantile_residual_before=probs[(code-2)*2]['root'],quantile_residual_after=probs[(code-2)*2+1]['root']))
  for name,s in score.items():
   valid=(role==code)&domain&np.isfinite(s);sel=select&np.isfinite(s)
   common=np.array([all(np.any(z&k&(bins==j)) for z in [valid,sel] for k in [L,H]) for j in range(5)]);r=ref*common;mass=float(r.sum());r/=r.sum()
   std=np.zeros(n)
   for j in range(5):
    gaps.append(dict(role=role_name,score=name,bin_low_GeV=50+10*j,common=bool(common[j]),L_N=int((valid&L&(bins==j)).sum()),H_N=int((valid&H&(bins==j)).sum()),mid_N=int((valid&~L&~H&(bins==j)).sum()),fixed_reference_mass=float(ref[j])))
    if not common[j]:continue
    for k in [L,H]:
     z=valid&k&(bins==j);std[z]=weight[z]*r[j]/weight[z].sum()
    z=valid&(L|H)&(bins==j);fp,tp,auc,pauc=curve(s[z],label[z],weight[z]);rocrows.append(dict(role=role_name,score=name,scope=f'pz{50+10*j}_{60+10*j}',AUC=auc,pAUC_0_10=pauc,AUC_low95=None,AUC_high95=None,pAUC_low95=None,pAUC_high95=None,L_N=int((z&L).sum()),H_N=int((z&H).sum()),reference_mass_retained=mass))
   z=std>0;fp,tp,auc,pauc=curve(s[z],label[z],std[z]);ROC_boot=[];bstd=np.zeros_like(dw)
   for j in np.flatnonzero(common):
    for k in [L,H]:
     cell=(valid&k&(bins==j))[use];a=dw[:,cell]*W[cell];den=a.sum(1);bstd[:,cell]=np.divide(a*r[j],den[:,None],out=np.full_like(a,np.nan),where=den[:,None]>0)
   small=z[use]
   for rep in range(500):
    bw=bstd[rep,small]
    if np.isfinite(bw).all() and bw.sum()>0:ROC_boot.append(curve(s[use][small],label[use][small],bw)[2:])
   aa=np.array(ROC_boot);ac=ci(aa[:,0]);pc=ci(aa[:,1]);rocrows.append(dict(role=role_name,score=name,scope='common_pz_standardized',AUC=auc,pAUC_0_10=pauc,AUC_low95=ac[0],AUC_high95=ac[1],pAUC_low95=pc[0],pAUC_high95=pc[1],L_N=int((z&L).sum()),H_N=int((z&H).sum()),reference_mass_retained=mass))
   for f,tpr in zip(fp,tp):curve_rows.append(dict(role=role_name,score=name,FPR=float(f),TPR=float(tpr)))
   for alpha in [.02,.05,.1]:
    threshold=thresholds[name,alpha];row=dict(role=role_name,score=name,nominal_FPR=alpha,threshold=threshold,reference_mass_retained=mass)
    for k,lab in [(L,'L_FPR'),(H,'H_TPR')]:
     usek=(z&k)[use];pred=s[use]>threshold;val=float(std[(z&k)&(s>threshold)].sum());bounds=ci(np.sum(bstd[:,usek]*pred[usek],axis=1));row.update({lab:val,lab+'_low95':bounds[0],lab+'_high95':bounds[1],lab+'_N':int(usek.sum()),lab+'_incoming':int(len(np.unique(dd['key_id'][usek]))),lab+'_raw_recognized':int((usek&pred).sum())})
    wp.append(row)
   for cls,mask in [('L',L),('mid100_200',(d['truth_E_GeV']>=100)&(d['truth_E_GeV']<200)),('below50',d['truth_E_GeV']<50),('H',H)]:
    zz=valid&mask;support.append(dict(role=role_name,score=name,diagnostic_class=cls,N=int(zz.sum()),incoming=len(np.unique(d['key_id'][zz])),weight_sum=float(weight[zz].sum()),undefined_scores=int(((role==code)&domain&mask&~np.isfinite(s)).sum())))
 table('point_risks.tsv',risk);table('loss_decomposition.tsv',decomp);table('probability.tsv',probrows);table('PIT.tsv',pitrows);table('ROC.tsv',rocrows);table('ROC_curve.tsv',curve_rows);table('working_points.tsv',wp);table('diagnostic_support.tsv',support);table('pz_support.tsv',gaps)
 child=resource.getrusage(resource.RUSAGE_CHILDREN);save('A_complete.json',dict(passed=True,roles={str(k):int((role==k).sum()) for k in [1,2,3]},new_energy_fits=0,scalar_calibrations=1,new_posterior_integrations=0,point_unchanged=True,bootstrap_repeats=500,CPU_self_s=time.process_time()-cpu,CPU_child_s=child.ru_utime+child.ru_stime,wall_s=time.perf_counter()-start,peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,maximum_event_decomposition_residual=max(x['identity_max_abs'] for x in decomp)))
 print((O/'A_complete.json').read_text(),flush=True)
if __name__=='__main__':main()
