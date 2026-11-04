"""Independent batch audit of frozen Stage99 outputs; zero optimizer/model steps."""
import csv,json,math,time,resource
from pathlib import Path
import numpy as np
from scipy.special import logsumexp,ndtr
from scipy.stats import norm
from energy_probability_scale import mean_preserving_log_scale
from stage99_report import boot,ci,table,save
R=Path(__file__).resolve().parents[1];O=R/'workbook/stage99_energy_ml'
def read(p):return list(csv.DictReader((R/p).open(),delimiter='\t'))
def main():
 tick=time.perf_counter();cpu=time.process_time();c=json.loads((O/'calibration.json').read_text());T=c['T'];b=c['b_fixed'];d=dict(np.load(R/'ntuples/energy_ml_stage94/evaluation_input.npz'));h=dict(np.load(R/'ml/artifacts/stage94/MDN_heads.npz'));raw=dict(np.load(R/'ml/artifacts/stage94/point_predictions.npz'));part=dict(np.load(R/'ntuples/energy_ml_stage94/cal_partition.npz'));idx=np.searchsorted(d['row'],h['row']);m=np.log(d['pz'][idx]/.8);y=np.log(d['truth_E_GeV'][idx]);ww=[];mm=[];ss=[]
 for k in sorted(set(h)-{'row'}):
  x=h[k].astype(float);ww.append(np.exp(x[:,:3]-logsumexp(x[:,:3],axis=1)[:,None])/3);mm.append(x[:,3:6]+m[:,None]);ss.append(.05+np.logaddexp(0,x[:,6:9]))
 w=np.column_stack(ww);mu=np.column_stack(mm);sig=np.column_stack(ss);center=(w*mu).sum(1);point=raw['E_ensemble'].astype(float)+b
 nm,ns,out=mean_preserving_log_scale(w,mu,sig,b,T,point[idx]);assert np.array_equal(out,point[idx]);meanerr=float(np.max(abs((w*nm).sum(1)-center-b)));assert meanerr<1e-12
 var=(w*(sig**2+(mu-center[:,None])**2)).sum(1);varnew=(w*(ns**2+(nm-center[:,None]-b)**2)).sum(1);verr=float(np.max(abs(varnew-T*T*var)));assert verr<1e-12
 postrow=part['row'][part['subrole']==2];ix=np.searchsorted(h['row'],postrow);assert np.array_equal(h['row'][ix],postrow);wp=part['weight'][part['subrole']==2]
 z=y[ix,None]-center[ix,None]-b;delta=mu[ix]-center[ix,None];sc=sig[ix];lp=np.log(w[ix])-np.log(T*sc)-.5*((z/T-delta)/sc)**2-.5*math.log(2*math.pi);resp=np.exp(lp-logsumexp(lp,axis=1)[:,None]);grad=-np.average((resp*(-1/T+z*(z/T-delta)/(T*T*sc*sc))).sum(1),weights=wp);assert abs(grad)<1e-6
 independent_checks=[]
 risks=read('workbook/stage99_energy_ml/point_risks.tsv');prior=read('workbook/stage94_energy_ml/metrics.tsv');scores=read('workbook/stage94_energy_ml/scores.tsv');prob=read('workbook/stage99_energy_ml/probability.tsv')
 for r in risks:
  name='E_ensemble_cal' if r['model']=='E94_ensemble' else r['model']
  if r['model']=='posterior92':continue
  matches=[v for v in prior if v['role']==r['role'] and v['stratum']==r['stratum'] and v['policy']==name and v['weighting']=='incoming']
  if matches:
   err=abs(float(r['log_RMSE'])-float(matches[0]['log_RMSE']));assert err<1e-12;independent_checks.append(dict(check='point_RMSE_vs_stage94',role=r['role'],group=r['stratum'],value=err))
 for r in prob:
  if r['stage']!='before':continue
  matches=[v for v in scores if v['role']==r['role'] and v['stratum']==r['stratum'] and v['model']=='E_ensemble_cal']
  if matches:
   err=abs(float(r['NLL'])-float(matches[0]['logE_NLL']));assert err<1e-12;independent_checks.append(dict(check='NLL_vs_stage94',role=r['role'],group=r['stratum'],value=err))
 # Validate every risk-decomposition aggregate independently using reported RMSE.
 riskmap={(r['role'],r['stratum'],r['model']):float(r['log_RMSE']) for r in risks}
 for r in read('workbook/stage99_energy_ml/loss_decomposition.tsv'):
  key=(r['role'],r['stratum']);delta=riskmap[key+(r['model'],)]**2-riskmap[key+('traditional',)]**2;err=abs(delta-float(r['E_c2'])-float(r['two_E_e0c']));assert err<1e-12;independent_checks.append(dict(check='aggregate_risk_identity',role=key[0],group=key[1],value=err))
 # Independent density/CDF checks on the predesignated first40 cal identities only.
 qa=json.loads((O/'QA.json').read_text());qix=np.searchsorted(h['row'],qa['rows']);density=(w[qix]*norm.pdf(y[qix,None],loc=nm[qix],scale=ns[qix])).sum(1);ld=logsumexp(np.log(w[qix])+norm.logpdf(y[qix,None],loc=nm[qix],scale=ns[qix]),axis=1);densityerr=float(np.max(abs(np.log(density)-ld)));assert densityerr<1e-12
 # Reconstruct pilot scores and the paired500 incoming intervals from saved outputs.
 bp=R/'ntuples/energy_ml_stage99/B_classifier_predictions.tsv';pilot_checks=0
 if bp.exists():
  p=read('ntuples/energy_ml_stage99/B_classifier_predictions.tsv');co=json.loads((R/'ntuples/energy_ml_stage95/cohort.json').read_text());lookup={x['row']:x for x in co['records']};rows=np.array([int(x['row']) for x in p]);labels=np.array([int(x['label']) for x in p]);sub=dict(key_id=np.array([lookup[r]['key_id'] for r in rows]),component=np.array([lookup[r]['component'] for r in rows]));gid,draw=boot(sub,2026110499);bw=draw[:,gid];den=bw.sum(1);losses=[]
  for model in [k for k in ['A','B'] if k in p[0]]:
   q=np.clip(np.array([float(x[model]) for x in p]),1e-12,1-1e-12);ll=-(labels*np.log(q)+(1-labels)*np.log1p(-q));br=(q-labels)**2;losses.append([ll,br]);stored=next(r for r in read('workbook/stage99_energy_ml/B_classifier_metrics.tsv') if r['model']==model)
   for name,v in [('logscore',ll),('Brier',br)]:
    bounds=ci(bw@v/den)
    for a,bv in [(float(v.mean()),float(stored[name])),(bounds[0],float(stored[name+'_low95'])),(bounds[1],float(stored[name+'_high95']))]:assert abs(a-bv)<1e-12;pilot_checks+=1
  for j,name in enumerate(['logscore','Brier']) if len(losses)==2 else []:
   v=losses[1][j]-losses[0][j];bounds=ci(bw@v/den);stored=next(r for r in read('workbook/stage99_energy_ml/B_classifier_delta.tsv') if r['metric']==name)
   for a,bv in [(v.mean(),float(stored['B_minus_A'])),(bounds[0],float(stored['low95'])),(bounds[1],float(stored['high95']))]:assert abs(a-bv)<1e-12;pilot_checks+=1
 table('independent_checks.tsv',independent_checks)
 # Conditional ROC intervals in every frozen pz bin, and actual continuous
 # point risks within each train/cal-frozen score threshold region.
 base=dict(np.load(R/'ml/artifacts/stage87/predictions.npz'));ib=np.searchsorted(base['row'],d['row']);q94=np.full(len(d['row']),np.nan);low=(w*(ndtr((np.log(100)-mu-b)/sig)-ndtr((np.log(50)-mu-b)/sig))).sum(1);high=(w*ndtr((mu+b-np.log(200))/sig)).sum(1);q94[idx]=np.divide(high,low+high,out=np.full(len(high),np.nan),where=low+high>0)
 sscores={'pz0':d['pz'].astype(float),'direct_cal_saved':base['direct_cal'][ib],'E94_mass_ratio':q94,'stage92_mass_ratio':np.full(len(d['row']),np.nan)};points={'pz0':np.log(d['pz']/.8),'direct_cal_saved':base['direct_cal'][ib],'E94_mass_ratio':point,'stage92_mass_ratio':np.full(len(d['row']),np.nan)}
 ratio=np.array(json.loads((R/'workbook/stage87_energy_ml/prior.json').read_text())['ratios']['nominal'])
 for rn,code in [('cal',2),('test',3)]:
  old=dict(np.load(R/f'ntuples/energy_ml_stage92/predictions_{rn}.npz'));z=d['role']==code;mass=np.diff(old['accurate_F'])*ratio;Lmass=mass[:,1];Hmass=mass[:,3:].sum(1);sscores['stage92_mass_ratio'][z]=np.divide(Hmass,Lmass+Hmass,out=np.full(len(Hmass),np.nan),where=Lmass+Hmass>0);points['stage92_mass_ratio'][z]=old['accurate_quantiles'][:,2]
 thresholds=read('workbook/stage99_energy_ml/thresholds.tsv');binrows=[];riskrows=[]
 from stage99_report import curve
 for rn,code in [('cal',2),('test',3)]:
  use=np.flatnonzero(d['role']==code);sub={k:v[use] for k,v in d.items()};gid,draw=boot(sub,2026110499+code);bw=draw[:,gid];ww=d['weight'][use];E=d['truth_E_GeV'][use];Y=np.log(E);LH=((E>=50)&(E<100))|(E>=200);lab=(E>=200).astype(int);pz=d['pz'][use];domain=(pz>50)&(pz<100)
  for name,score in sscores.items():
   sv=score[use];pv=points[name][use]
   for lo in [50,60,70,80,90]:
    z=domain&LH&(pz>=lo)&(pz<lo+10)&np.isfinite(sv);vals=[]
    if len(set(lab[z]))<2:continue
    for rep in range(500):
     rw=bw[rep,z]*ww[z]
     if all(rw[lab[z]==cls].sum()>0 for cls in [0,1]):vals.append(curve(sv[z],lab[z],rw)[2:])
    vals=np.array(vals);ac=ci(vals[:,0]);pc=ci(vals[:,1]);_,_,auc,pauc=curve(sv[z],lab[z],ww[z]);binrows.append(dict(role=rn,score=name,pz_low_GeV=lo,pz_high_GeV=lo+10,L_N=int((lab[z]==0).sum()),H_N=int((lab[z]==1).sum()),AUC=auc,AUC_low95=ac[0],AUC_high95=ac[1],pAUC_0_10=pauc,pAUC_low95=pc[0],pAUC_high95=pc[1],valid_draws=len(vals)))
   for th in [r for r in thresholds if r['score']==name]:
    t=float(th['threshold']);alpha=float(th['alpha'])
    for region,z in [('all',domain),('score_above',domain&(sv>t)),('score_at_or_below',domain&(sv<=t))]:
     z=z&np.isfinite(sv);error=pv-Y;a=bw[:,z]*ww[z];den=a.sum(1);loss=error[z]**2;bs=np.sqrt(np.divide(a@loss,den,out=np.full(len(den),np.nan),where=den>0));bounds=ci(bs);rel=np.expm1(error[z]);riskrows.append(dict(role=rn,score=name,nominal_FPR=alpha,region=region,N=int(z.sum()),incoming=len(np.unique(sub['key_id'][z])),E50_100_N=int((z&(E>=50)&(E<100)).sum()),E100_200_N=int((z&(E>=100)&(E<200)).sum()),E200plus_N=int((z&(E>=200)).sum()),mean_true_E_GeV=float(np.average(E[z],weights=ww[z])),point_log_RMSE=float(np.sqrt(np.average(loss,weights=ww[z]))),RMSE_low95=bounds[0],RMSE_high95=bounds[1],point_tail50_pct=float(100*np.average(abs(rel)>.5,weights=ww[z])),new_gate=False))
 table('ROC_within_pz_CI.tsv',binrows);table('working_point_energy_risks.tsv',riskrows)
 # Compact scientific figure, generated on batch with standard plotting tools.
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(1,3,figsize=(13,3.7),layout='constrained')
 rr=read('workbook/stage99_energy_ml/ROC_curve.tsv')
 for score in ['pz0','direct_cal_saved','E94_mass_ratio','stage92_mass_ratio']:
  z=[r for r in rr if r['role']=='test' and r['score']==score];axes[0].plot([float(r['FPR']) for r in z],[float(r['TPR']) for r in z],label=score)
 axes[0].set(xlim=(0,.2),ylim=(0,1),xlabel='Standardized low-E false-positive rate',ylabel='High-E recognition',title='Developed test: same low pz support');axes[0].legend(fontsize=7)
 pit=read('workbook/stage99_energy_ml/PIT.tsv')
 for st in ['before','after']:
  z=[r for r in pit if r['role']=='test' and r['stratum']=='all' and r['stage']==st];axes[1].plot(np.arange(10)+.5,[float(r['fraction']) for r in z],marker='o',label=st)
 axes[1].axhline(.1,color='gray',ls='--');axes[1].set(xlabel='PIT bin',ylabel='Weighted fraction',title='One mean-preserving scale');axes[1].legend()
 dep=read('workbook/stage99_energy_ml/loss_decomposition.tsv');groups=['E50_100','pz50_100_trueE200','all']
 for j,term in enumerate(['E_c2','two_E_e0c','risk_delta']):
  vals=[float(next(r for r in dep if r['role']=='test' and r['model']=='E94_ensemble' and r['stratum']==g)[term]) for g in groups];axes[2].bar(np.arange(3)+(j-1)*.25,vals,width=.25,label=term)
 axes[2].axhline(0,color='gray');axes[2].set(xticks=np.arange(3),xticklabels=['true low E','low pz / high E','all'],ylabel='Squared log-energy risk',title='E94 correction vs traditional');axes[2].legend(fontsize=7)
 fig.savefig(O/'diagnostics.pdf');fig.savefig(O/'diagnostics.png',dpi=160);plt.close(fig)
 save('validation.json',dict(passed=True,optimizer_steps=0,new_fits=0,stored_point_exact=True,analytic_mean_max=meanerr,variance_scale_max=verr,NLL_temperature_gradient=float(grad),independent_density40_max=densityerr,previous_output_and_identity_checks=len(independent_checks),pilot_scalar_and_interval_checks=pilot_checks,max_report_check_error=max(x['value'] for x in independent_checks),CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,peak_RSS_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024))
if __name__=='__main__':main()
