"""Correct the same-N control's canonical family accounting, without tuning."""
import json

import numpy as np

import stage119_fitcurve as f
from stage119_curve_common import OUT,load


def main():
    old=load('ntuples/energy_ml_stage119/old_input.npz');new=load('ntuples/energy_ml_stage119/curve_input.npz');p=json.loads((OUT/'curve_protocol.json').read_text())
    rows=f.control(old,new);assert rows is not None
    lock=dict(correction='old_same_N counted response-cell memberships, leading1316 unique families instead of1320. Use canonical-family cells and globally unique selection; no change to any curve or augmented fit.',
        original_same_N_retained_as_invalid_control=True,name='old_same_N_fixed',old_rows=rows.tolist(),old_unique_incoming=len(np.unique(old['incoming'][rows],axis=0)),new_curve_families=p['scales'][-1],
        unchanged='original fixed policy/seeds/rounds/calibration; no change selected by outcome')
    (OUT/'same_N_correction_lock.json').write_text(json.dumps(lock,indent=2)+'\n')
    f.G=old,new,p;result=f.fit(('old_same_N_fixed',rows,np.array([],int)))
    fits=json.loads((OUT/'fits.json').read_text());fits['results']=[r for r in fits['results'] if r['policy']!='old_same_N']+[result]
    fits['control_correction']=lock['correction'];fits['correction_CPU_s']=result['CPU_s']
    (OUT/'fits_final.json').write_text(json.dumps(fits,indent=2)+'\n')
    print(lock['correction'],result,flush=True)


if __name__=='__main__':main()
