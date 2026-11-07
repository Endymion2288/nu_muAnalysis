"""Measured charge recovery/coverage/cost with source-held real ADC clipping."""
import json
import resource
import time

import numpy as np

from stage129_energy import OUT, CACHE, load, table
from stage129_waveform import templates, recover


def main():
    tick,cpu=time.perf_counter(),time.process_time()
    indices=[0,48,113]
    inputs={i:load(CACHE/f'pilot2_{i}.npz') for i in indices}
    official={i:json.loads((OUT/f'official_{i}.json').read_text()) for i in indices}
    models={};policy=[]
    for channel in [14,6,7]:
        controls=[]
        d=inputs[0]
        for r in official[0]['original']:
            if r['channel']!=channel or r['official'][0]!=0:continue
            i=int(np.flatnonzero(d['row']==r['row'])[0]);j=d['channel'][i].tolist().index(channel)
            if not (d['adc'][i,j]==0).any():controls.append(d['adc'][i,j])
        # Official window contains both endpoints, hence stop491 for980ns.
        model=templates(controls,[390,491])
        models[channel]=model
        policy.append(dict(channel=channel,controls=model['controls'],sigma_ADC=model['sigma'],rho=model['rho'],baseline_sigma_ADC=model['baseline_sigma'],centre_sample=model['centre'],window_samples=model['window']))
    results=[]
    for index in indices:
        d=inputs[index]
        for r in official[index]['artificial_controls']:
            channel=r['channel'];i=int(np.flatnonzero(d['row']==r['row'])[0]);j=d['channel'][i].tolist().index(channel)
            clipped=np.maximum(d['adc'][i,j].astype(int)-r['ADC_shift'],0)
            recovered=recover(clipped,models[channel])
            results.append(dict(source=index,row=r['row'],channel=channel,fraction=r['fraction'],target_pC=r['target_pC'],
                                raw_pC=r['clipped_official'][1],CB_pC=r['clipped_official'][2],CB_status=r['clipped_official'][0],**recovered))
    groups=[]
    for index in indices:
        for channel in [14,6,7]:
            for fraction in [.75,.5,.25]:
                group=[r for r in results if r['source']==index and r['channel']==channel and r['fraction']==fraction]
                if not group:continue
                valid=[r for r in group if r['available']]
                for method,key in [('raw','raw_pC'),('official_CB','CB_pC'),('constrained','Q_pC')]:
                    selected=valid if method=='constrained' else group
                    delta=np.array([r[key]-r['target_pC'] for r in selected])
                    relative=np.array([(r[key]-r['target_pC'])/r['target_pC'] for r in selected])
                    groups.append(dict(source=index,channel=channel,fraction=fraction,method=method,
                                       parent_controls=len(group),available=len(selected),failure_N=len(group)-len(selected),
                                       bias_pC=float(delta.mean()) if len(delta) else None,RMSE_pC=float(np.sqrt(np.mean(delta**2))) if len(delta) else None,
                                       relative_RMSE=float(np.sqrt(np.mean(relative**2))) if len(delta) else None,
                                       nominal95_coverage=float(np.mean([r['lower95_pC']<=r['target_pC']<=r['upper95_pC'] for r in selected])) if method=='constrained' and selected else None,
                                       template_scope='train_source0' if index==0 else 'source_held_validation'))
    table('recovery_pilot.tsv',groups)
    table('pilot_templates.tsv',policy)
    (OUT/'recovery_pilot_summary.json').write_text(json.dumps(dict(controls=len(results),independent_parent_controls=len({(r['source'],r['row'],r['channel']) for r in results}),
        available=sum(r['available'] for r in results),template_sources=[0],held_sources=[48,113],artificial_repeats_increase_parent_N=False,
        failed_reasons={k:sum(r['profile_status']==k for r in results) for k in sorted({r['profile_status'] for r in results})},
        CPU_s=time.process_time()-cpu,wall_s=time.perf_counter()-tick,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        scope='cost and finite-window ADC recovery, not energy or PMT response validation'),indent=2)+'\n')
    np.savez_compressed(CACHE/'recovery_pilot.npz',**{k:np.array([r[k] for r in results]) for k in results[0]})
    print('RECOVERY_PILOT',len(results),sum(r['available'] for r in results),time.perf_counter()-tick,flush=True)


if __name__=='__main__':main()
