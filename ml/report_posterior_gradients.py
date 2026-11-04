"""Stage90 independent saved-array validation and numerical summaries; no integrations."""
import csv,json,sys
from pathlib import Path
import numpy as np
from support_augmentation import arrays,save,table,begin,resources
from audit_posterior_gradients import OUT,CACHE,NAMES

def read(name):return list(csv.DictReader((OUT/name).open(),delimiter='\t'))
start=begin();d=arrays(CACHE/'input.npz');v=arrays(CACHE/'audit_values.npz')
np.testing.assert_array_equal(d['row'],v['row']);events=read('audit_events.tsv');grad=read('audit_gradients.tsv')
assert len(events)==552 and len(grad)==552*17
for i,r in enumerate(events):assert int(r['row'])==int(d['row'][i])
fd=v['reference_gradient'];unc=v['reference_uncertainty'];tol=1e-4+1e-3*abs(fd)
acc=abs(v['gradient']-fd)+unc<=tol;resolved=unc<=tol/4;ghpass=abs(v['GH32_gradient']-fd)+unc<=tol
checks=0;maximum=0.
for i in range(552):
 for j in range(17):
  r=grad[i*17+j];assert int(r['row'])==int(d['row'][i]) and r['parameter']==NAMES[j]
  for key,a in [('accurate_gradient',v['gradient'][i,j]),('reference_gradient',fd[i,j]),('reference_uncertainty',unc[i,j]),('step_disagreement',v['reference_step_difference'][i,j]),('GH32_gradient',v['GH32_gradient'][i,j]),('accurate_error',abs(v['gradient'][i,j]-fd[i,j])),('GH32_error',abs(v['GH32_gradient'][i,j]-fd[i,j]))]:
   diff=abs(float(r[key])-a);assert diff<1e-12;maximum=max(maximum,float(diff));checks+=1
  assert (r['accurate_pass']=='True')==acc[i,j]
  assert (r['reference_resolved']=='True')==resolved[i,j]
  assert (r['GH32_pass']=='True')==ghpass[i,j]
 valuepass=abs(v['value'][i]-v['reference_value'][i])+float(events[i]['reference_log_error'])<=1e-6
 assert (events[i]['certified']=='True')==bool(valuepass and (acc[i]&resolved[i]).all())
rows=[];byparameter=[];groups=[]
for role,name in [(1,'train'),(2,'cal')]:
 m=d['role']==role;w=d['weight'][m];w=w/w.sum();N=int(m.sum())
 def avg(a):return np.average(a[m],weights=w,axis=0)
 a=avg(v['gradient']);g=avg(v['GH32_gradient']);ref=avg(fd);noise=avg(unc)
 joint=avg(v['joint_gradient']);accurate_train=-joint-.25*a[:15];GHtrain=-joint-.25*g[:15]
 cosine=float(np.dot(accurate_train,GHtrain)/(np.linalg.norm(accurate_train)*np.linalg.norm(GHtrain)))
 delta=v['gradient'][m,:15]-v['GH32_gradient'][m,:15]
 total=-v['joint_gradient'][m]-.25*v['gradient'][m,:15]
 loss_delta=.25*np.linalg.norm(delta,axis=1)
 relative_delta=loss_delta/np.maximum(np.linalg.norm(total,axis=1),1e-15)
 rows.append(dict(role=name,N=N,weight_sum=float(d['weight'][m].sum()),certified_N=sum(events[i]['certified']=='True' for i in np.flatnonzero(m)),
  accurate_NLL=float(-avg(v['value'])),GH32_NLL=float(-avg(v['GH32_value'])),
  GH32_value_error_gt_0p000001_N=int((abs(v['GH32_value'][m]-v['reference_value'][m])>1e-6).sum()),
  GH32_any_gradient_failed_events=int((~ghpass[m]).any(1).sum()),GH32_failed_coordinates=int((~ghpass[m]).sum()),
  accurate_failed_coordinates=int((~acc[m]).sum()),unresolved_reference_coordinates=int((~resolved[m]).sum()),
  max_accurate_value_error=float(abs(v['value'][m]-v['reference_value'][m]).max()),
  max_GH32_value_error=float(abs(v['GH32_value'][m]-v['reference_value'][m]).max()),
  max_accurate_gradient_error=float(abs(v['gradient'][m]-fd[m]).max()),
  max_GH32_gradient_error=float(abs(v['GH32_gradient'][m]-fd[m]).max()),
  mean_head_gradient_difference_L2=float(np.linalg.norm(a[:15]-g[:15])),
  mean_negative_joint_quarter_marginal_gradient_accurate_L2=float(np.linalg.norm(accurate_train)),
  mean_negative_joint_quarter_marginal_gradient_GH32_L2=float(np.linalg.norm(GHtrain)),
  mean_negative_joint_quarter_marginal_cosine=cosine,
  mean_negative_joint_quarter_marginal_difference_L2=float(.25*np.linalg.norm(a[:15]-g[:15])),
  quarter_marginal_head_gradient_difference_L2_median=float(np.median(loss_delta)),
  quarter_marginal_head_gradient_difference_L2_p95=float(np.quantile(loss_delta,.95)),
  total_loss_relative_gradient_difference_median=float(np.median(relative_delta)),
  total_loss_relative_gradient_difference_p95=float(np.quantile(relative_delta,.95)),
  training_loss_interpretation='actual training parameter point' if role==1 else 'cal-head hypothetical sensitivity only; cal optimizer varies b/T, not head',
  max_reference_uncertainty=float(unc[m].max()),max_reference_uncertainty_over_tolerance=float((unc[m]/tol[m]).max())))
 for j,namepar in enumerate(NAMES):
  byparameter.append(dict(role=name,parameter=namepar,accurate_mean_NLL_gradient=float(-a[j]),GH32_mean_NLL_gradient=float(-g[j]),
   reference_mean_NLL_gradient=float(-ref[j]),reference_uncertainty=float(noise[j]),
   GH32_failed_N=int((~ghpass[m,j]).sum()),accurate_failed_N=int((~acc[m,j]).sum()),
   max_accurate_error=float(abs(v['gradient'][m,j]-fd[m,j]).max()),max_GH32_error=float(abs(v['GH32_gradient'][m,j]-fd[m,j]).max())))
 # No incoming bootstrap: finite numerical audit, not population fit-risk claim.
 for layer,mask in [('all',np.ones(len(m),bool)),('E50_100',(d['truth_E_GeV']>=50)&(d['truth_E_GeV']<100)),('E100_200',(d['truth_E_GeV']>=100)&(d['truth_E_GeV']<200)),('pz50_100',d['pz']<100),('high_y',d['y_lepton']>=.8),('fit_failure',d['fit_failure'])]:
  mm=m&mask
  if not mm.any():continue
  groups.append(dict(role=name,stratum=layer,N=int(mm.sum()),GH32_any_gradient_failure_N=int((~ghpass[mm]).any(1).sum()),max_GH32_value_error=float(abs(v['GH32_value'][mm]-v['reference_value'][mm]).max()),max_GH32_gradient_error=float(abs(v['GH32_gradient'][mm]-fd[mm]).max())))
table(OUT/'role_summary.tsv',rows);table(OUT/'parameter_summary.tsv',byparameter);table(OUT/'strata_summary.tsv',groups)
save(OUT/'independent_validation.json',dict(passed=True,rows=552,coordinate_checks=9384,checked_numeric_values=checks,max_difference=maximum,
 all_certified=bool(acc.all() and resolved.all() and all(r['certified']=='True' for r in events)),
 independent_source='separate saved-array arithmetic, strict event and parameter identity, all flags/means independently reconstructed; FD is from original unchanged Reference',
 population_intervals='未测量; numerical audit only',training_trajectory='未测量',new_fits=0,**resources(start)))
print(json.dumps(rows,ensure_ascii=False,indent=2))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(1,2,figsize=(10,4),layout='constrained')
for method,color in [('gradient','#009e73'),('GH32_gradient','#d55e00')]:
    error=(abs(v[method]-fd)+unc)/tol
    x=np.sort(error.ravel())
    axes[0].plot(np.maximum(x,1e-14),np.arange(1,len(x)+1)/len(x),color=color,label='Accurate score' if method=='gradient' else 'Original GH32')
axes[0].axvline(1,color='grey',ls='--',lw=1)
axes[0].set_xscale('log');axes[0].set_xlabel('Gradient discrepancy / frozen tolerance')
axes[0].set_ylabel('Fraction of 9,384 coordinates');axes[0].legend(fontsize=8)
axes[0].set_title('Includes reference uncertainty')
cal=[r for r in byparameter if r['role']=='cal' and r['parameter'] in ['b','T']]
x=np.arange(2)
for shift,key,label,color in [(-.12,'GH32_mean_NLL_gradient','GH32','#d55e00'),(.12,'accurate_mean_NLL_gradient','Accurate','#009e73')]:
    axes[1].bar(x+shift,[r[key] for r in cal],width=.24,color=color,label=label)
axes[1].axhline(0,color='grey',lw=.7);axes[1].set_xticks(x,['b','T'])
axes[1].set_ylabel('Weighted mean raw NLL derivative')
axes[1].set_title('Fixed cal512 at original b/T; no optimization');axes[1].legend(fontsize=8)
fig.suptitle('Stage90 numerical audit: fixed 40 train / 512 cal final heads\nNo new fit, calibration optimization or test evaluation',fontsize=10)
svg=OUT/'gradient_audit.svg';fig.savefig(svg);svg.write_text('\n'.join(x.rstrip() for x in svg.read_text().splitlines())+'\n')
fig.savefig('/tmp/stage90_gradient_audit.png',dpi=140);plt.close(fig)
save(OUT/'report_resources.json',resources(start))
