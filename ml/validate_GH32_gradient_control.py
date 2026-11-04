"""Fixed stage90 four-cal independent numpy GH32 derivative control."""
import sys
import numpy as np,torch
from pathlib import Path
from support_augmentation import arrays,save,begin,resources
from transfer_posterior import log_energy_density
from posterior_numerics import FixedGH
start=begin();d=arrays(Path('ntuples/energy_ml_stage90/qa_input.npz'));v=arrays(Path('ntuples/energy_ml_stage90/qa_values.npz'))
maximum=0.;count=0
for i in range(4):
 x=np.r_[d['head'][i].astype(float),d['b'][i],d['T'][i]]
 for j in range(17):
  gs=[]
  for step in [1e-4,5e-5]:
   yy=[]
   for sign in [-1,1]:
    xx=x.copy();xx[j]+=sign*step
    f=FixedGH(xx[:15][None],d['pz'][i:i+1],xx[15],xx[16],32)
    yy.append(np.log(f.evaluate(np.log(d['truth_E_GeV'][i:i+1]),density=True)[1][0,0]))
   gs.append((yy[1]-yy[0])/(2*step))
  ref=(4*gs[1]-gs[0])/3;diff=abs(ref-v['GH32_gradient'][i,j]);maximum=max(maximum,float(diff));count+=1
  assert diff<1e-7+1e-5*abs(ref),(i,j,diff)
save(Path('workbook/stage90_energy_ml/GH32_autograd_control.json'),dict(passed=True,fixed_cal_N=4,coordinates=count,
 maximum_gradient_difference=maximum,source='independent numpy FixedGH and dual-step Richardson versus original torchGH32 autograd; no accurate integrals rerun',**resources(start)))
print(maximum)
