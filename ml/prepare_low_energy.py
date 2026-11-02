import csv,json,re
from pathlib import Path
repo=Path.cwd(); out=repo/'workbook/stage55_energy_ml'
assert not (repo/'ml/configs/low_energy.json').exists(), 'Frozen protocol already exists; do not regenerate it'
base=list(csv.DictReader(open('ml/configs/files.tsv'),delimiter='\t')); rows=[]
nominal={200082,200083,200089,200093,200094,200100}
for r in base:
 if int(r['run']) in nominal and r['partition'] in ['train','validation','calibration']:
  rows.append(dict(index=len(rows),run=int(r['run']),component=r['component'],family='nominal',group=r['group'],partition=r['partition'],input=r['input'],rdo='',old_index=int(r['index'])))
for run in range(200080,200102):
 if run in nominal:continue
 paths=sorted(Path(f'/eos/experiment/fasernu-data0/faser/sim/mc24/genie/{run}/rdo/s0014').glob('*.root'))
 stem=paths[0].name; comp='charm' if 'charm' in stem else ('pi' if '_pi-' in stem else 'k')
 selected=['00000-00009','00010-00019','00080-00089' if comp=='k' else '00020-00029']
 for j,s in enumerate(selected):
  p=next(p for p in paths if f'-{s}-' in p.name)
  old=next((r for r in base if r['input_rdo']==str(p)),None)
  rows.append(dict(index=len(rows),run=run,component=comp,family=p.name.split('-')[1].split('Genie_',1)[-1],group=f'{comp}:{s}',partition='train' if j<2 else 'validation',input=old['input'] if old else '',rdo=str(p),old_index=int(old['index']) if old else -1))
with open('ml/configs/low_energy_files.tsv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\n');w.writeheader();w.writerows(rows)
# Low-energy selection differs by exactly two momentum thresholds; strip histograms only.
import yaml
cuts=yaml.safe_load(open('AnalysisZipFramework/config/cuts.yaml')); cuts['Histograms']=[]
for k,v in list(cuts['Cuts'].items()):
 v.pop('histograms',None)
 if k in ['Truth pz > 100 GeV','Track pz > 100 GeV']:
  v['expression']=v['expression'].replace('> 100','> 50')
  cuts['Cuts'][k.replace('100','50')]=cuts['Cuts'].pop(k)
# Preserve original cut order.
original=yaml.safe_load(open('AnalysisZipFramework/config/cuts.yaml'))
cuts['Cuts']={k.replace('100','50') if k in ['Truth pz > 100 GeV','Track pz > 100 GeV'] else k:cuts['Cuts'][k.replace('100','50') if k in ['Truth pz > 100 GeV','Track pz > 100 GeV'] else k] for k in original['Cuts']}
Path('AnalysisZipFramework/config/ml_low_energy_cuts.yaml').write_text(yaml.safe_dump(cuts,sort_keys=False))
cfg=dict(stage=55,reason='User prioritizes low energy bias, 50-100 GeV and alternative flux training',thresholds_GeV=dict(truth_pz=50,reco_pz=50),selection='original cuts except truth and reconstructed pz thresholds 100 -> 50; no truth E ceiling',nominal_runs=sorted(nominal),alternative_runs=sorted(set(range(200080,200102))-nominal),alternative_groups_per_run=3,alternative_train_groups=2,alternative_evaluation_groups=1,reconstruction='official master d32b0ff3 merge without IFT TI12MC04 FASERNU-04 OFLCOND-FASER-06',feature_version='F6: exact original 46+19 deployment features',seed_indices=[0,1,2],rounds=400,xgboost=dict(max_depth=5,eta=.04,subsample=.8,colsample_bytree=1.,min_child_weight=20,reg_lambda=10,tree_method='hist',nthread=1,objective='reg:squarederror'),candidates=['nominal100','nominal50','mixture50','residual50','matched_flux50'],maximum_formal_fits=15,maximum_smoke_fits=1,calibration='one common nominal calibration cohort pz>50; additive mean log offset for each model; raw also reported',energy_edges_GeV=[50,75,100,150,200,400,800,1600,3200,6400],momentum_edges_GeV=[50,75,100,150,250,1000],bootstrap_replicates=500,bootstrap_seed=2026110255,weights='unit MC, no physical flux normalization; mixture effect includes model and component/prior changes',support='development comparison; old calibration/validation/challenge exposed; not new independent confirmation',gate='report paired source confidence intervals vs p/0.8 separately for E 50-100,100-200 and reco p 50-100,100-250; no posthoc model selection',leakage='group role consistent by component and generation range across run geometry and alternative flux; remove exact incoming-neutrino (pdg,px,py,pz) overlap with calibration/evaluation from training before fits; complete generation lineage independence unproven; exclude calibration incoming-neutrino vectors present in evaluation',full_file_extraction=True,maximum_new_reconstruction_files=sum(not r['input'] for r in rows))
Path('ml/configs/low_energy.json').write_text(json.dumps(cfg,indent=2)+'\n')
print('sources',len(rows),'new reco',cfg['maximum_new_reconstruction_files'])
for part in ['train','validation','calibration']:
 print(part,sum(r['partition']==part for r in rows),'nominal',sum(r['partition']==part and r['run'] in nominal for r in rows))
