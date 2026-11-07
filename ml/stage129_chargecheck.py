"""Matched charge comparisons and source-held empirical interval validation."""
import json,sys,time
import numpy as np
from scipy.signal import find_peaks
from stage129_energy import OUT,CACHE,load,table


def main():
 pilot=int(sys.argv[1])==0;name='chargecov_pilot' if pilot else 'chargecov'
 a=load(CACHE/('artificial_recoverycov_pilot.npz' if pilot else 'artificial_recoverycov.npz'));c=load(CACHE/'controls.npz');official={}
 for i in range(4):
  d=load(CACHE/f'officialfull_{i}.npz')
  for j in range(len(d['control'])):official[(int(d['control'][j]),float(d['fraction'][j]))]={k:v[j] for k,v in d.items()}
 target=np.array([official[(int(i),float(f))]['target_pC'] for i,f in zip(a['control'],a['fraction'])]);cb=np.array([official[(int(i),float(f))]['CB_pC'] for i,f in zip(a['control'],a['fraction'])]);raw=np.array([official[(int(i),float(f))]['raw_pC'] for i,f in zip(a['control'],a['fraction'])]);cbstat=np.array([official[(int(i),float(f))]['CB_status'] for i,f in zip(a['control'],a['fraction'])]);available=a['available'];factors={};policies=[]
 peakclass=[]
 for i in a['control']:
  wave=c['adc'][i].astype(float);signal=wave[:75].mean()-wave[390:491];sigma=wave[:75].std();peaks,_=find_peaks(signal,prominence=max(5*sigma,.1*signal.max()),distance=3);peakclass.append('multi_peak' if len(peaks)>1 else 'single_peak')
 peakclass=np.asarray(peakclass)
 for ch in [14,6,7]:
  use=(a['role']==2)&(a['channel']==ch)&available
  delta=target[use]-a['Q_pC'][use];half=np.where(delta>=0,a['upper95_pC'][use]-a['Q_pC'][use],a['Q_pC'][use]-a['lower95_pC'][use]);viewscore=np.abs(delta)/np.maximum(half,1e-12)
  controls=a['control'][use];score=np.array([np.max(viewscore[controls==c]) for c in np.unique(controls)]);n=len(score)
  if n>=20:
   rank=min(n,int(np.ceil(.95*(n+1))));factor=max(1.,float(np.sort(score)[rank-1]))
  else:factor=None
  factors[ch]=factor;policies.append(dict(channel=ch,calibration_artificial_views=int(use.sum()),calibration_unique_controls=n,calibration_unique_parents=len(set(a['row'][use])),side_halfwidth_inflation=factor,quantile='percontrol max across available rails, ceil(.95*(ncontrols+1)) order, floor1; source exchangeability not certified',applied_to_energy=not pilot))
 calibrated_low=a['lower95_pC'].copy();calibrated_high=a['upper95_pC'].copy()
 for ch,factor in factors.items():
  use=a['channel']==ch
  if factor is None:calibrated_low[use]=np.nan;calibrated_high[use]=np.nan
  else:
   calibrated_low[use]=a['Q_pC'][use]-factor*(a['Q_pC'][use]-a['lower95_pC'][use]);calibrated_high[use]=a['Q_pC'][use]+factor*(a['upper95_pC'][use]-a['Q_pC'][use])
 rows=[]
 for role in [2,3]:
  for ch in [14,6,7]:
   for frac in [.75,.5,.25]:
    for shape in ['all','single_peak','multi_peak']:
     use=(a['role']==role)&(a['channel']==ch)&(a['fraction']==frac)
     if shape!='all':use &= peakclass==shape
     if not use.any():continue
     for subset in ['all_controls','common_available']:
      keep=use if subset=='all_controls' else use&available
      for method,value in [('clipped_raw',raw),('official_CB',cb),('constrained',a['Q_pC'])]:
       finite=keep&np.isfinite(value);err=value[finite]-target[finite]
       record=dict(role=role,channel=ch,fraction=frac,shape=shape,subset=subset,method=method,parent_channel_controls=int(use.sum()),subset_N=int(keep.sum()),evaluated_N=int(finite.sum()),unique_parent_N=len(set(a['row'][keep])),unavailable_N=int((use&~available).sum()),bias_pC=float(err.mean()) if len(err) else None,RMSE_pC=float(np.sqrt(np.mean(err**2))) if len(err) else None,relative_RMSE=float(np.sqrt(np.mean((err/target[finite])**2))) if len(err) else None,official_failure_N=int((use&(((cbstat.astype(int)&(16|32|8|128|256))!=0)|~np.isfinite(cb))).sum()))
       if method=='constrained' and finite.any():
        record.update(nominal95_coverage=float(np.mean((a['lower95_pC'][finite]<=target[finite])&(target[finite]<=a['upper95_pC'][finite]))),calibrated95_coverage=float(np.mean((calibrated_low[finite]<=target[finite])&(target[finite]<=calibrated_high[finite]))),median_calibrated_width_pC=float(np.median(calibrated_high[finite]-calibrated_low[finite])))
        src=a['source'][finite];unique=np.unique(src);rng=np.random.default_rng(202611071290)
        covered=(calibrated_low[finite]<=target[finite])&(target[finite]<=calibrated_high[finite]);coverage=[]
        if len(unique)>=2:
         nums=np.array([covered[src==s].sum() for s in unique]);dens=np.array([(src==s).sum() for s in unique]);draw=rng.multinomial(len(unique),np.full(len(unique),1/len(unique)),size=500);coverage=(draw@nums)/(draw@dens)
        low,high=np.quantile(coverage,[.025,.975]).tolist() if len(coverage) else [None,None]
        record.update(calibrated_coverage_source_low95=low,calibrated_coverage_source_high95=high,source_N=len(unique))
       rows.append(record)
 table(name+'_comparison.tsv',rows);table(name+'_interval_calibration.tsv',policies)
 summary=dict(pilot=pilot,artificial_views=len(target),independent_parent_channel_controls=len(set(zip(a['row'].tolist(),a['channel'].tolist()))),unique_parent_N=len(set(a['row'])),available=int(available.sum()),nominal_coverage=float(np.mean((a['lower95_pC'][available]<=target[available])&(target[available]<=a['upper95_pC'][available]))),same_window='780-980ns inclusive, original official raw target, clipped officialraw/CB sameW',artificial_scope='ADC truncation only, not PMT or scintillator nonlinearity',calibration_scope='source-role2 calibrated halfwidth, role3source-held evaluation; nominal profile with plug-in templatecov not exactlikelihood',template_sources='originaltrain only, sourceheld controls',direct_integral_target_max_abs_pC=float(np.max(abs(a['target_pC']-target))))
 (OUT/(name+'_summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
 if not pilot:(OUT/'recovery_interval_policy.json').write_text(json.dumps({str(ch):factor for ch,factor in factors.items()},indent=2)+'\n')
 print(summary,flush=True)

if __name__=='__main__':main()
