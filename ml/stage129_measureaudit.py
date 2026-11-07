"""Diagnose whole-population template rejection before any new energy risk."""
import json,resource,time
import numpy as np
from stage129_energy import OUT,CACHE,load,table
from stage129_recover import read_models,model_for
from stage129_waveform import templates

def main():
 tick=time.perf_counter();plan=json.loads((OUT/'extraction_contract.json').read_text());models=read_models();rows=[]
 for si in [0,48,113]:
  a=load(CACHE/f'extract_{si}.npz');s=plan['requests'][si]
  for j,ch in enumerate(a['channel'][0]):
   ch=int(ch)
   if ch not in [14,6,7]:continue
   m=model_for(models,s['run'],ch);r=load(CACHE/f'recover_{si//14}.npz')
   use=(r['source']==si)&(r['channel']==ch);chi=r['chi2_ndof'][use]
   wave=a['adc'][:,j].astype(float);valid=a['present'][:,j];base=wave[:,:75].mean(1);signal=base[:,None]-wave[:,390:491];clipped=(wave[:,390:491]==0).any(1)&valid
   clean=valid&~clipped&(a['scalar'][:,[14,6,7].index(ch)+2,0]==0)&((base-wave[:,390:491].min(1))>20)
   # Actual noise-free shape variability left outside the frozen two-PC space.
   shapes=[]
   for i in np.flatnonzero(clean):
    peak=int(np.argmax(signal[i]));v=np.interp(np.arange(101)+(peak-(m['centre']-390)),np.arange(101),signal[i]);shapes.append(v/signal[i,peak])
   if shapes:
    shapes=np.asarray(shapes);project=np.linalg.lstsq(m['pc'],(shapes-m['mean']).T,rcond=None)[0].T;res=shapes-m['mean']-project@m['pc'].T;left=np.sqrt(np.mean(res**2))
   else:left=np.nan
   rows.append(dict(source=si,channel=ch,actual_clipped_N=int(clipped.sum()),finite_chi2_N=int(np.isfinite(chi).sum()),median_chi2_ndof=float(np.nanmedian(chi)),p05_chi2_ndof=float(np.nanquantile(chi,.05)),training_shape_residual_fraction=float(left),electronic_sigma_ADC=m['sigma'],clipped_level_median_ADC=float(np.median(base[clipped])),omitted_shape_sigma_at_rail_ADC=float(left*np.median(base[clipped])),centre_sample=m['centre']))
 table('recovery_model_audit.tsv',rows);print(rows,flush=True)
if __name__=='__main__':main()
