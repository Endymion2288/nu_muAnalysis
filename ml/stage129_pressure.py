"""Predeclared sensor perturbations on held controls; never train on stress data."""
import json
import multiprocessing as mp
import time

import numpy as np

from stage129_energy import OUT, CACHE, load, table
from stage129_recovercov import read_models, model_for
from stage129_waveformcov import recover


def work(task):
    meta, adc, template, rail = task
    return dict(**meta, **recover(adc, template, rail))


def main():
    tick=time.perf_counter();c=load(CACHE/'controls.npz');models=read_models();tasks=[]
    plan=json.loads((OUT/'pressure_protocol.json').read_text())
    for i in range(0,len(c['row']),32):
        adc=c['adc'][i].astype(float);base=adc[:75].mean();signal=base-adc;peak=np.argmax(signal);grid=np.arange(600)
        model=model_for(models,int(c['run'][i]),int(c['channel'][i]))
        for name in plan['wave_variants']:
            s=signal.copy();ramp=np.zeros(600);floor=0;assumed=0
            if name.startswith('gain'):s*=1+float(name.split(':')[1])
            if name.startswith('width'):s=np.interp(peak+(grid-peak)/(1+float(name.split(':')[1])),grid,signal)
            if name.startswith('baseline'):ramp=float(name.split(':')[1])*(grid-37)/490
            if name.startswith('shift'):s=np.interp(grid-float(name.split(':')[1])/2,grid,signal)
            if name.startswith('rail'):
                floor=int(name.split(':')[1]);assumed=floor if name.endswith('known') else 0
            truth=.04*2/16.384*s[390:491].sum()
            uncut=base-s+ramp;shift=int(np.floor(base-.5*s.max()))
            wave=np.maximum(np.rint(uncut-shift),floor)
            tasks.append((dict(control=i,row=int(c['row'][i]),role=int(c['role'][i]),channel=int(c['channel'][i]),variant=name,target_pC=truth),wave,model,assumed))
    with mp.get_context('fork').Pool(4) as pool:records=pool.map(work,tasks,chunksize=8)
    np.savez_compressed(CACHE/'wave_pressure.npz',**{k:np.asarray([r[k] for r in records]) for k in records[0]})
    factors=json.loads((OUT/'recovery_interval_policy.json').read_text());rows=[]
    for role in [2,3]:
        for variant in plan['wave_variants']:
            for ch in [14,6,7]:
                group=[r for r in records if r['role']==role and r['variant']==variant and r['channel']==ch];ok=[r for r in group if r['available']]
                if not group:continue
                err=np.array([r['Q_pC']-r['target_pC'] for r in ok]);factor=factors[str(ch)]
                coverage=[r['Q_pC']-factor*(r['Q_pC']-r['lower95_pC'])<=r['target_pC']<=r['Q_pC']+factor*(r['upper95_pC']-r['Q_pC']) for r in ok]
                rows.append(dict(role=role,variant=variant,channel=ch,N=len(group),available=len(ok),RMSE_pC=float(np.sqrt(np.mean(err**2))) if len(ok) else None,bias_pC=float(err.mean()) if len(ok) else None,calibrated_coverage=float(np.mean(coverage)) if len(ok) else None))
    table('wave_pressure.tsv',rows)
    (OUT/'wave_pressure_summary.json').write_text(json.dumps(dict(views=len(records),unique_controls=len(set(r['control'] for r in records)),wall_s=time.perf_counter()-tick,scope='synthetic bounded sensor stress, not calibrated 1sigma systematics or real PMT saturation truth; baseline ramps reference underlying no-ramp pulse'),indent=2)+'\n')


if __name__=='__main__':main()
