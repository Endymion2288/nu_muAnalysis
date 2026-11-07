"""Complete the measured template uncertainty omitted in the first GLS version."""
import json,time
from pathlib import Path
import numpy as np
from stage129_energy import OUT,CACHE,load,table
from stage129_recover import read_models

def main():
 tick=time.perf_counter();models=read_models();plan=json.loads((OUT/'extraction_contract.json').read_text());data={k:[] for k in models}
 for s in plan['requests']:
  if not any(c['role']==1 for c in s['cases']):continue
  path=CACHE/f'extract_{s["index"]}.npz'
  if not path.exists():path=Path('/eos/user/x/xcheng/FASER/nu_muAnalysis/ntuples/energy_ml_stage129')/path.name
  a=load(path);role=np.array([c['role'] for c in s['cases']]);names=a['names'].tolist()
  for j,ch in enumerate(a['channel'][0]):
   ch=int(ch)
   if ch not in [14,6,7]:continue
   col={14:2,6:3,7:4}[ch];wave=a['adc'][:,j].astype(float);base=wave[:,:75].mean(1);peak=base-wave[:,390:491].min(1)
   clean=(role==1)&a['present'][:,j]&(a['scalar'][:,col,0]==0)&~(wave==0).any(1)&(peak>20)
   for key in [f'pool_{ch}',f'{s["run"]}_{ch}']:
    if key not in models:continue
    m=models[key];grid=np.arange(101);shape=[]
    for i in np.flatnonzero(clean):
     sig=base[i]-wave[i];pk=int(np.argmax(sig[390:491]))+390
     if sig[pk]>10*m['sigma']:shape.append(np.interp(grid+390+(pk-m['centre']),np.arange(600),sig)/sig[pk])
    data[key].extend(shape)
 rows=[]
 for key,m in models.items():
  a=np.asarray(data[key]);assert len(a)==m['controls'],(key,len(a),m['controls'])
  coeff=np.linalg.lstsq(m['pc'],(a-m['mean']).T,rcond=None)[0].T;res=a-m['mean']-coeff@m['pc'].T
  m['shape_cov']=res.T@res/max(1,len(res)-1)
  rows.append(dict(template=key,controls=len(a),omitted_shape_RMS_fraction=float(np.sqrt(np.trace(m['shape_cov'])/101))))
 (OUT/'templates_cov.json').write_text(json.dumps({key:{k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in m.items()} for key,m in models.items()},separators=(',',':'))+'\n');table('template_covariance.tsv',rows)
 print('SHAPE_COVARIANCE',len(models),time.perf_counter()-tick,flush=True)

if __name__=='__main__':main()
