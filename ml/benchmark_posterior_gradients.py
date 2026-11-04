"""Fixed four-cal stage90 first-order density timing; zero fitting."""
import sys,time
import numpy as np,torch
from differentiable_posterior import log_energy_density
from transfer_posterior import log_energy_density as gh
from support_augmentation import arrays,save,begin,resources
from pathlib import Path
start=begin();torch.set_num_threads(1);d=arrays(Path('ntuples/energy_ml_stage90/qa_input.npz'))
results=[]
# Four fixedcal QA identities only, two timed repetitions; timing, no optimizer.
for name,fn in [('GH32',gh),('adaptive_score',log_energy_density)]:
 times=[]
 for rep in range(2):
  h=torch.tensor(d['head'].astype(float),requires_grad=True)
  b=torch.tensor(d['b'][0],dtype=torch.float64,requires_grad=True);T=torch.tensor(d['T'][0],dtype=torch.float64,requires_grad=True)
  z=torch.tensor(np.log(d['truth_E_GeV']));p=torch.tensor(d['pz'])
  tick=time.process_time();v=fn(h,z,p,b,T);(-v.mean()).backward();times.append(time.process_time()-tick)
 results.append(dict(method=name,N=4,repetitions=2,forward_backward_CPU_s=times,CPU_s_per_event_mean=float(np.mean(times)/4),optimizer_steps=0,network_forwards=0))
# Transparent extrapolation: finalhead tinycal timings are not a training estimate.
per=results[1]['CPU_s_per_event_mean'];training_events=46575*150
save(Path('workbook/stage90_energy_ml/benchmark.json'),dict(results=results,nominal_training_event_evaluations=training_events,
 projected_scalar_density_forward_backward_CPU_s=per*training_events,projection_scope='4 fixed finalcal heads, CPUfloat64 scalar-integral VJP, excludes network/joint/preprocessing/validation/calibration; not measured training runtime or a guaranteed bound',
 zero_fits=True,**resources(start)))
print(results, 'projected scalar CPU s',per*training_events)
