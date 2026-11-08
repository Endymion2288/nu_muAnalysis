"""Returned shape diagnostics only; generated on the full batch worker."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from stage196_measure import CACHE,OUT,read_gz

s=read_gz(CACHE/'full_science.json.gz')
fig,axes=plt.subplots(2,3,figsize=(12,7),sharey=True)
for detector,ax in zip(['Calo','Calo2','VetoNu','Veto','Trigger','Preshower'],axes.flat):
    real=[r['residual_over_baseline_RMS'] for r in s['data_rows'] if r['detector']==detector and r['subset']=='last32' and r.get('residual_over_baseline_RMS') is not None]
    random=[r['residual_over_baseline_RMS'] for r in s['random_rows'] if r['channel'].split(':')[0]==detector and r.get('residual_over_baseline_RMS') is not None]
    for label,values in [('Real held-out primary status0',real),('Random fixed ADC samples',random)]:
        if values:ax.step(sorted(values),np.arange(1,len(values)+1)/len(values),where='post',label=f'{label} N={len(values)}')
    ax.set_xscale('symlog',linthresh=.01);ax.set_title(detector);ax.set_ylim(0,1.02)
    ax.set_xlabel('Residual RMS / measured baseline RMS')
    ax.set_ylabel('Empirical CDF');ax.legend(fontsize=7)
fig.suptitle('Empirical-template residuals; random controls do not identify physical source')
fig.tight_layout()
for ext in ['png','svg']:fig.savefig(OUT/f'actual_shape_residuals.{ext}',dpi=150)
plt.close(fig)
fig,ax=plt.subplots(figsize=(7,4))
for detector in ['Calo','VetoNu','Veto','Trigger','Preshower']:
    rows=[r for r in s['MC_rows'] if r['detector']==detector and r.get('residual_over_MC_noise_RMS') is not None]
    if rows:ax.scatter([r['corrected_hit_RMS_ns'] for r in rows],[r['residual_over_MC_noise_RMS'] for r in rows],s=18,label=f'{detector} N={len(rows)}')
ax.set_xscale('symlog',linthresh=.01);ax.set_yscale('symlog',linthresh=.001)
ax.set_xlabel('MC energy-weighted corrected-hit time RMS [ns]')
ax.set_ylabel('Ideal residual RMS / MC noise RMS')
ax.set_title('Original12 MC, original status0 only; truth-informed time collapse')
ax.legend(fontsize=8);fig.tight_layout()
for ext in ['png','svg']:fig.savefig(OUT/f'MC_time_collapse.{ext}',dpi=150)
plt.close(fig)
for path in OUT.glob('*.svg'):path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
